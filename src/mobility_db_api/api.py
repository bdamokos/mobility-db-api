import os
import requests
import json
import hashlib
import csv
import time
import fcntl
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import zipfile
from unidecode import unidecode
from dotenv import load_dotenv
import shutil
from .logger import setup_logger
from .csv_catalog import CSVCatalog

# Load environment variables
load_dotenv()

@dataclass
class DatasetMetadata:
    """Metadata for a downloaded GTFS dataset"""
    provider_id: str
    provider_name: str
    dataset_id: str
    download_date: datetime
    source_url: str
    is_direct_source: bool
    api_provided_hash: Optional[str]
    file_hash: str
    download_path: Path
    feed_start_date: Optional[str] = None
    feed_end_date: Optional[str] = None

class MetadataLock:
    """Context manager for safely reading/writing metadata file"""
    def __init__(self, metadata_file: Path, mode: str):
        self.file = open(metadata_file, mode)
        self.mode = mode
    
    def __enter__(self):
        # Use exclusive lock for writing, shared lock for reading
        fcntl.flock(self.file.fileno(), 
                   fcntl.LOCK_EX if 'w' in self.mode else fcntl.LOCK_SH)
        return self.file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()

class MobilityAPI:
    """A client for interacting with the Mobility Database API.

    This class provides methods to search for GTFS providers, download datasets,
    and manage downloaded data. It handles authentication, caching, and metadata
    tracking automatically.

    The client can operate in two modes:
    1. API mode (default): Uses the Mobility Database API with authentication
    2. CSV mode: Uses the CSV catalog when no API key is provided or when force_csv_mode is True

    Attributes:
        data_dir (Path): Directory where downloaded datasets are stored
        refresh_token (str): Token used for API authentication
        datasets (Dict): Dictionary of downloaded dataset metadata
        force_csv_mode (bool): If True, always use CSV catalog even if API key is available

    Example:
        >>> api = MobilityAPI(data_dir="data")  # Will try API first, fallback to CSV
        >>> api_csv = MobilityAPI(force_csv_mode=True)  # Will always use CSV
        >>> providers = api.get_providers_by_country("HU")
        >>> dataset_path = api.download_latest_dataset("tld-5862")
    """
    
    def __init__(self, data_dir: str = "data", refresh_token: Optional[str] = None,
                 log_level: str = "INFO", logger_name: str = "mobility_db_api",
                 force_csv_mode: bool = False):
        """
        Initialize the API client.
        
        Args:
            data_dir: Base directory for all GTFS downloads
            refresh_token: Optional refresh token. If not provided, will try to load from .env file
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
            logger_name: Name for the logger instance. Defaults to 'mobility_db_api'.
            force_csv_mode: If True, always use CSV catalog even if API key is available.
        """
        # Set up logger with instance-specific name if needed
        self.logger = setup_logger(name=f"{logger_name}_{data_dir}", level=log_level)
        self.logger.debug("Initializing MobilityAPI client")

        self.base_url = "https://api.mobilitydatabase.org/v1"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.data_dir / "datasets_metadata.json"
        self.refresh_token = refresh_token
        self._last_metadata_mtime = None
        self._load_metadata()
        
        # CSV catalog is initialized lazily
        self._csv_catalog = None
        self.force_csv_mode = force_csv_mode
        self._use_csv = force_csv_mode
        
        if not force_csv_mode:
            # Try to get an access token, fallback to CSV if it fails
            if not self.get_access_token():
                self.logger.info("No valid API token found, falling back to CSV catalog")
                self._use_csv = True

    @property
    def csv_catalog(self) -> CSVCatalog:
        """Lazy initialization of CSV catalog."""
        if self._csv_catalog is None:
            self.logger.debug("Initializing CSV catalog")
            self._csv_catalog = CSVCatalog(cache_dir=str(self.data_dir / "csv_cache"))
        return self._csv_catalog

    def _get_metadata_file(self, base_dir: Optional[Path] = None) -> Path:
        """Get the appropriate metadata file path based on the base directory"""
        if base_dir is None:
            return self.metadata_file
        return base_dir / "datasets_metadata.json"

    def _get_metadata_mtime(self) -> Optional[float]:
        """Get the last modification time of the metadata file"""
        try:
            return self.metadata_file.stat().st_mtime if self.metadata_file.exists() else None
        except OSError:
            return None

    def _has_metadata_changed(self) -> bool:
        """Check if the metadata file has been modified since last load"""
        current_mtime = self._get_metadata_mtime()
        if current_mtime is None:
            return False
        if self._last_metadata_mtime is None:
            return True
        return current_mtime > self._last_metadata_mtime

    def _load_metadata(self):
        """Load existing metadata from file with file locking"""
        self.datasets: Dict[str, DatasetMetadata] = {}
        if self.metadata_file.exists():
            try:
                with MetadataLock(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    for key, item in data.items():
                        self.datasets[key] = DatasetMetadata(
                            provider_id=item['provider_id'],
                            provider_name=item.get('provider_name', 'Unknown Provider'),
                            dataset_id=item['dataset_id'],
                            download_date=datetime.fromisoformat(item['download_date']),
                            source_url=item['source_url'],
                            is_direct_source=item['is_direct_source'],
                            api_provided_hash=item.get('api_provided_hash'),
                            file_hash=item['file_hash'],
                            download_path=Path(item['download_path']),
                            feed_start_date=item.get('feed_start_date'),
                            feed_end_date=item.get('feed_end_date')
                        )
                    # Update last modification time after successful load
                    self._last_metadata_mtime = self._get_metadata_mtime()
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.error(f"Error loading metadata: {str(e)}")
                self.datasets = {}
                self._last_metadata_mtime = None

    def _save_metadata(self, base_dir: Optional[Path] = None):
        """
        Save current metadata to file with file locking.
        If base_dir is provided, saves metadata to that directory instead of the default.
        """
        metadata_file = self._get_metadata_file(base_dir)
        
        # Filter datasets to only include those in the target directory
        target_datasets = {
            key: meta for key, meta in self.datasets.items()
            if base_dir is None or str(meta.download_path).startswith(str(base_dir))
        }
        
        try:
            # Ensure the file exists before opening in r+ mode
            if not metadata_file.exists():
                metadata_file.touch()
            
            # Use a single exclusive lock for both read and write
            with MetadataLock(metadata_file, 'r+') as f:
                # Read existing metadata
                existing_data = {}
                try:
                    f.seek(0)
                    content = f.read()
                    if content:  # Only try to parse if file is not empty
                        existing_data = json.loads(content)
                except json.JSONDecodeError:
                    self.logger.warning("Could not read existing metadata, will overwrite")
                
                # Merge new data with existing data
                data = existing_data.copy()
                data.update({
                    key: {
                        'provider_id': meta.provider_id,
                        'provider_name': meta.provider_name,
                        'dataset_id': meta.dataset_id,
                        'download_date': meta.download_date.isoformat(),
                        'source_url': meta.source_url,
                        'is_direct_source': meta.is_direct_source,
                        'api_provided_hash': meta.api_provided_hash,
                        'file_hash': meta.file_hash,
                        'download_path': str(meta.download_path),
                        'feed_start_date': meta.feed_start_date,
                        'feed_end_date': meta.feed_end_date
                    }
                    for key, meta in target_datasets.items()
                })
                
                # Write merged data
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
            
            # Update last modification time after successful save
            if base_dir is None:
                self._last_metadata_mtime = self._get_metadata_mtime()
            else:
                # If saving to a different directory, update mtime if it's our main metadata file
                if metadata_file == self.metadata_file:
                    self._last_metadata_mtime = self._get_metadata_mtime()
        except IOError as e:
            self.logger.error(f"Error saving metadata: {str(e)}")

    def reload_metadata(self, force: bool = False):
        """
        Reload metadata from file if it has been modified or if forced.
        
        Args:
            force: If True, reload metadata regardless of modification time.
                  If False, only reload if the file has been modified.
        
        Returns:
            bool: True if metadata was reloaded, False if no reload was needed
        """
        if force or self._has_metadata_changed():
            self._load_metadata()
            return True
        return False

    def ensure_metadata_current(self) -> bool:
        """
        Ensure the in-memory metadata is current with the file.
        This is a convenience method that should be called before
        any operation that reads from the metadata.
        
        Returns:
            bool: True if metadata was reloaded, False if no reload was needed
        """
        return self.reload_metadata(force=False)

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token for API authentication.

        This method handles token refresh automatically when needed. It uses the
        refresh token to obtain a new access token from the API.

        Returns:
            A valid access token string if successful, None if token refresh fails
            or if no refresh token is available.

        Example:
            >>> api = MobilityAPI()
            >>> token = api.get_access_token()
            >>> if token:
            ...     print(token)
            ...     'eyJ0eXAiOiJKV1QiLCJhbGc...'
            ... else:
            ...     print("Using CSV fallback mode")
        """
        if not self.refresh_token:
            self.refresh_token = os.getenv("MOBILITY_API_REFRESH_TOKEN")
        if not self.refresh_token:
            self.logger.debug("No refresh token provided and none found in .env file")
            return None
        
        url = f"{self.base_url}/tokens"
        headers = {"Content-Type": "application/json"}
        data = {"refresh_token": self.refresh_token}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            return None
        except Exception as e:
            self.logger.error(f"Exception during token request: {str(e)}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with access token for API requests.
        
        Returns:
            Dictionary of headers. If no token is available, returns empty headers.
        """
        token = self.get_access_token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def get_providers_by_country(self, country_code: str) -> List[Dict]:
        """Search for GTFS providers by country code.

        Args:
            country_code: Two-letter ISO country code (e.g., "HU" for Hungary)

        Returns:
            List of provider dictionaries containing provider information.
            Each dictionary includes:
                - id: Provider's unique identifier
                - provider: Provider's name
                - country: Provider's country
                - source_info: Information about data sources

        Example:
            >>> api = MobilityAPI()
            >>> providers = api.get_providers_by_country("HU")
            >>> for p in providers:
            ...     print(f"{p['provider']}: {p['id']}")
            'BKK: o-u-dr_bkk'
        """
        if self._use_csv:
            return self.csv_catalog.get_providers_by_country(country_code)
        
        url = f"{self.base_url}/gtfs_feeds"
        params = {"country_code": country_code.upper()}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            # If API request fails, try CSV fallback
            self.logger.warning("API request failed, falling back to CSV catalog")
            self._use_csv = True
            return self.csv_catalog.get_providers_by_country(country_code)

    def get_providers_by_name(self, name: str) -> List[Dict]:
        """Search for providers by name.
        
        Args:
            name: Provider name to search for (case-insensitive partial match)
        
        Returns:
            List of matching provider dictionaries.
        """
        if self._use_csv:
            return self.csv_catalog.get_providers_by_name(name)
        
        url = f"{self.base_url}/gtfs_feeds"
        params = {"provider": name}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            # If API request fails, try CSV fallback
            self.logger.warning("API request failed, falling back to CSV catalog")
            self._use_csv = True
            return self.csv_catalog.get_providers_by_name(name)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_feed_dates(self, extract_dir: Path) -> Tuple[Optional[str], Optional[str]]:
        """Extract feed start and end dates from feed_info.txt if available"""
        feed_info_path = extract_dir / "feed_info.txt"
        if not feed_info_path.exists():
            return None, None
        
        try:
            with open(feed_info_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                row = next(reader)
                return (
                    row.get('feed_start_date'),
                    row.get('feed_end_date')
                )
        except (StopIteration, KeyError, csv.Error):
            return None, None

    def _get_directory_size(self, path: Path) -> int:
        """Calculate total size of a directory in bytes"""
        total = 0
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
        return total

    def _sanitize_provider_name(self, name: str) -> str:
        """
        Sanitize provider name for use in directory names.
        Converts Unicode characters to ASCII, removes special characters,
        and ensures the name is filesystem-friendly.
        """
        # Take only the first part before any comma or dash
        name = name.split(',')[0].split(' - ')[0].strip()
        
        # Convert to ASCII and remove special characters
        name = unidecode(name)
        
        # Replace spaces with underscores and remove any remaining non-alphanumeric characters
        name = ''.join(c if c.isalnum() else '_' for c in name)
        
        # Remove consecutive underscores and trim
        while '__' in name:
            name = name.replace('__', '_')
        name = name.strip('_')
        
        return name

    def download_latest_dataset(self, provider_id: str, download_dir: Optional[str] = None, use_direct_source: bool = False) -> Optional[Path]:
        """Download the latest GTFS dataset from a provider.

        This method handles both hosted and direct source downloads. It includes
        progress tracking, metadata collection, and automatic extraction of
        downloaded datasets.

        Args:
            provider_id: The unique identifier of the provider
            download_dir: Optional custom directory to store the dataset
            use_direct_source: Whether to use direct download URL instead of
                             hosted dataset. Defaults to False.

        Returns:
            Path to the extracted dataset directory if successful, None if download fails.
            The directory contains the extracted GTFS files (txt files).

        Example:
            >>> api = MobilityAPI()
            >>> dataset_path = api.download_latest_dataset("tld-5862")
            >>> print(dataset_path)
            PosixPath('mobility_datasets/volanbus_20240315')
        """
        try:
            # Get provider info based on mode
            if self._use_csv:
                # In CSV mode, get provider info from catalog
                provider_data = self.csv_catalog.get_provider_info(provider_id)
                if not provider_data:
                    self.logger.error(f"Provider {provider_id} not found in CSV catalog")
                    return None
            else:
                # In API mode, get provider info from the API
                self.logger.info(f"Fetching provider info for {provider_id}")
                url = f"{self.base_url}/gtfs_feeds/{provider_id}"
                response = requests.get(url, headers=self._get_headers())
                if response.status_code != 200:
                    self.logger.error(f"Failed to get provider info: {response.status_code}")
                    if response.status_code in (401, 403, 413):  # Auth errors or request too large
                        self.logger.info("Falling back to CSV catalog")
                        self._use_csv = True
                        return self.download_latest_dataset(provider_id, download_dir, use_direct_source)
                    return None
                provider_data = response.json()
            
            provider_name = provider_data.get('provider', 'Unknown Provider')
            latest_dataset = provider_data.get('latest_dataset')
            
            # For direct source, we don't need latest_dataset
            if use_direct_source:
                if not provider_data.get('source_info', {}).get('producer_url'):
                    self.logger.error("No direct download URL available for this provider")
                    return None
                download_url = provider_data['source_info']['producer_url']
                api_hash = None
                is_direct = True
                # Create a pseudo dataset ID for direct downloads
                latest_dataset = {
                    'id': f"direct_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                }
            else:
                if not latest_dataset:
                    self.logger.error(f"No latest dataset available for provider {provider_id}")
                    return None
                download_url = latest_dataset['hosted_url']
                api_hash = latest_dataset.get('hash')
                is_direct = False
            
            # Create provider directory with sanitized name
            safe_name = self._sanitize_provider_name(provider_name)
            base_dir = Path(download_dir) if download_dir else self.data_dir
            base_dir.mkdir(parents=True, exist_ok=True)
            provider_dir = base_dir / f"{provider_id}_{safe_name}"
            provider_dir.mkdir(exist_ok=True)
            
            # Check if we already have this dataset
            dataset_key = f"{provider_id}_{latest_dataset['id']}"
            old_dataset_id = None
            old_dataset_path = None
            
            # Find any existing dataset for this provider
            for key, meta in list(self.datasets.items()):
                if meta.provider_id == provider_id:
                    if dataset_key == key and meta.is_direct_source == is_direct:
                        if api_hash and api_hash == meta.api_provided_hash:
                            self.logger.info(f"Dataset {dataset_key} already exists and hash matches")
                            return meta.download_path
                        elif not api_hash and meta.download_path.exists():
                            # For direct source, download and compare file hash
                            self.logger.info("Checking if direct source dataset has changed...")
                            temp_file = provider_dir / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                            start_time = time.time()
                            response = requests.get(download_url)
                            download_time = time.time() - start_time
                            if response.status_code == 200:
                                with open(temp_file, 'wb') as f:
                                    f.write(response.content)
                                new_hash = self._calculate_file_hash(temp_file)
                                if new_hash == meta.file_hash:
                                    temp_file.unlink()
                                    self.logger.info(f"Dataset {dataset_key} already exists and content matches")
                                    return meta.download_path
                                # If hash different, continue with new download
                                temp_file.unlink()
                    # Store the old dataset info for later cleanup
                    old_dataset_id = meta.dataset_id
                    old_dataset_path = meta.download_path
                    # Remove old dataset from metadata now
                    del self.datasets[key]
            
            # Download dataset
            self.logger.info(f"Downloading dataset from {download_url}")
            start_time = time.time()
            response = requests.get(download_url)
            download_time = time.time() - start_time
            
            if response.status_code != 200:
                self.logger.error(f"Failed to download dataset: {response.status_code}")
                return None
            
            # Save and process the zip file
            zip_file = provider_dir / f"{latest_dataset['id']}.zip"
            with open(zip_file, 'wb') as f:
                f.write(response.content)
            
            zip_size = zip_file.stat().st_size
            self.logger.info(f"Download completed in {download_time:.2f} seconds")
            self.logger.info(f"Downloaded file size: {zip_size / 1024 / 1024:.2f} MB")
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(zip_file)
            
            # Extract dataset
            self.logger.info("Extracting dataset...")
            extract_dir = provider_dir / latest_dataset['id']
            start_time = time.time()
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            extract_time = time.time() - start_time
            
            extracted_size = self._get_directory_size(extract_dir)
            self.logger.info(f"Extraction completed in {extract_time:.2f} seconds")
            self.logger.info(f"Extracted size: {extracted_size / 1024 / 1024:.2f} MB")
            
            # Get feed dates from feed_info.txt
            feed_start_date, feed_end_date = self._get_feed_dates(extract_dir)
            if feed_start_date and feed_end_date:
                self.logger.info(f"Feed validity period: {feed_start_date} to {feed_end_date}")
            
            # Clean up zip file
            self.logger.info("Cleaning up downloaded zip file...")
            zip_file.unlink()
            
            # Save metadata
            metadata = DatasetMetadata(
                provider_id=provider_id,
                provider_name=provider_name,
                dataset_id=latest_dataset['id'],
                download_date=datetime.now(),
                source_url=download_url,
                is_direct_source=is_direct,
                api_provided_hash=api_hash,
                file_hash=file_hash,
                download_path=extract_dir,
                feed_start_date=feed_start_date,
                feed_end_date=feed_end_date
            )
            self.datasets[dataset_key] = metadata
            self._save_metadata()  # Save to main metadata file
            if download_dir:
                self._save_metadata(base_dir)  # Save to custom directory metadata file
            
            # Clean up old dataset if it exists
            if old_dataset_path and old_dataset_path.exists():
                self.logger.info(f"Cleaning up old dataset {old_dataset_id}...")
                shutil.rmtree(old_dataset_path)
            
            return extract_dir
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during download: {str(e)}")
            return None
        except (zipfile.BadZipFile, OSError) as e:
            self.logger.error(f"Error processing dataset: {str(e)}")
            return None

    def list_downloaded_datasets(self) -> List[DatasetMetadata]:
        """
        Get a list of all downloaded datasets in the data directory.
        
        Returns:
            List of DatasetMetadata objects for all downloaded datasets
        """
        return [meta for meta in self.datasets.values() 
                if meta.download_path.exists()]

    def _add_downloaded_dataset_info(self, provider_info: Dict) -> Dict:
        """Add downloaded dataset information to provider info if available.
        
        Args:
            provider_info: Provider information dictionary
            
        Returns:
            Updated provider information dictionary with downloaded dataset info if available
        """
        if not provider_info:
            return provider_info
            
        # Get provider ID and normalize it
        provider_id = provider_info['id']
        if provider_id.startswith('mdb-'):
            normalized_id = provider_id
        elif provider_id.isdigit():
            normalized_id = f"mdb-{provider_id}"
        else:
            normalized_id = provider_id  # Keep other formats (e.g., tld-1234) as is
            
        # Check if we have a downloaded dataset for this provider
        self.ensure_metadata_current()
        downloaded_datasets = [
            meta for meta in self.datasets.values()
            if meta.provider_id == normalized_id and meta.download_path.exists()
        ]
        
        if downloaded_datasets:
            # Sort by download date to get the latest
            downloaded_datasets.sort(key=lambda x: x.download_date, reverse=True)
            latest = downloaded_datasets[0]
            
            # Add downloaded dataset info to the provider info
            provider_info["downloaded_dataset"] = {
                "dataset_id": latest.dataset_id,
                "download_date": latest.download_date.isoformat(),
                "download_path": str(latest.download_path),
                "is_direct_source": latest.is_direct_source,
                "file_hash": latest.file_hash,
                "feed_start_date": latest.feed_start_date,
                "feed_end_date": latest.feed_end_date
            }
        
        return provider_info

    def get_provider_info(self, provider_id: str) -> Optional[Dict]:
        """
        Get information about a specific provider, including any downloaded dataset.
        
        This method combines provider information from either the API or CSV catalog
        with information about any downloaded dataset for this provider.
        
        Args:
            provider_id: The unique identifier of the provider
        
        Returns:
            Dictionary containing provider information and downloaded dataset details
            if available, None if the provider doesn't exist or is inactive/deprecated.
            
        Example:
            >>> api = MobilityAPI()
            >>> info = api.get_provider_info("mdb-123")
            >>> if info:
            ...     print(f"Provider: {info['provider']}")
            ...     if 'downloaded_dataset' in info:
            ...         print(f"Downloaded: {info['downloaded_dataset']['download_path']}")
        """
        # First try to get provider info from API or CSV
        if self._use_csv:
            provider_info = self.csv_catalog.get_provider_info(provider_id)
            if not provider_info:
                return None
            # Check for redirects
            if provider_info.get('redirects'):
                return None
            return self._add_downloaded_dataset_info(provider_info)
        
        try:
            url = f"{self.base_url}/gtfs_feeds/{provider_id}"
            response = requests.get(url, headers=self._get_headers())
            if response.status_code == 200:
                try:
                    provider_info = response.json()
                    # Check for redirects
                    if provider_info.get('redirects'):
                        return None
                    return self._add_downloaded_dataset_info(provider_info)
                except requests.exceptions.JSONDecodeError:
                    self.logger.warning("Invalid JSON response from API")
                    return None
            elif response.status_code in (401, 403, 413):  # Auth errors or request too large
                self.logger.info("Falling back to CSV catalog")
                self._use_csv = True
                return self.get_provider_info(provider_id)
            elif response.status_code == 404:
                return None
            else:
                self.logger.warning(f"API request failed with status {response.status_code}")
                self._use_csv = True  # Fall back to CSV on any other error
                return self.get_provider_info(provider_id)
        except requests.exceptions.RequestException:
            self.logger.warning("API request failed, falling back to CSV catalog")
            self._use_csv = True
            return self.get_provider_info(provider_id)
        
        return None

    def _cleanup_empty_provider_dir(self, provider_path: Path) -> None:
        """
        Clean up a provider directory if it's empty.
        Only removes the directory if it exists and contains no files or subdirectories.
        """
        try:
            if provider_path.exists():
                # Check if directory is empty (excluding metadata file)
                contents = list(provider_path.iterdir())
                if not contents or (len(contents) == 1 and contents[0].name == "datasets_metadata.json"):
                    shutil.rmtree(provider_path)
                    self.logger.info(f"Removed empty provider directory: {provider_path}")
        except Exception as e:
            self.logger.warning(f"Failed to clean up provider directory {provider_path}: {str(e)}")

    def delete_dataset(self, provider_id: str, dataset_id: Optional[str] = None) -> bool:
        """
        Delete a downloaded dataset.
        
        Args:
            provider_id: The ID of the provider
            dataset_id: Optional specific dataset ID. If not provided, deletes the latest dataset
        
        Returns:
            True if the dataset was deleted, False if it wasn't found or couldn't be deleted
        """
        # Find matching datasets
        matches = [
            (key, meta) for key, meta in self.datasets.items()
            if meta.provider_id == provider_id and
            (dataset_id is None or meta.dataset_id == dataset_id)
        ]
        
        if not matches:
            self.logger.error(f"No matching dataset found for provider {provider_id}")
            return False
        
        # If dataset_id not specified, take the latest one
        if dataset_id is None and len(matches) > 1:
            matches.sort(key=lambda x: x[1].download_date, reverse=True)
        
        key, meta = matches[0]
        provider_dir = meta.download_path.parent
        
        try:
            if meta.download_path.exists():
                shutil.rmtree(meta.download_path)
                self.logger.info(f"Deleted dataset directory: {meta.download_path}")
            
            # Remove from metadata
            del self.datasets[key]
            self._save_metadata()
            
            # Clean up provider directory if empty
            self._cleanup_empty_provider_dir(provider_dir)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting dataset: {str(e)}")
            return False

    def delete_provider_datasets(self, provider_id: str) -> bool:
        """
        Delete all downloaded datasets for a specific provider.
        
        Args:
            provider_id: The ID of the provider whose datasets should be deleted
            
        Returns:
            True if all datasets were deleted successfully, False if any deletion failed
        """
        # Find all datasets for this provider
        matches = [
            (key, meta) for key, meta in self.datasets.items()
            if meta.provider_id == provider_id
        ]
        
        if not matches:
            self.logger.error(f"No datasets found for provider {provider_id}")
            return False
        
        success = True
        provider_dir = None
        
        for key, meta in matches:
            try:
                if meta.download_path.exists():
                    shutil.rmtree(meta.download_path)
                    self.logger.info(f"Deleted dataset directory: {meta.download_path}")
                
                # Store provider directory for later cleanup
                provider_dir = meta.download_path.parent
                
                # Remove from metadata
                del self.datasets[key]
                
            except Exception as e:
                self.logger.error(f"Error deleting dataset {key}: {str(e)}")
                success = False
        
        # Save metadata after all deletions
        if success:
            self._save_metadata()
            
            # Clean up provider directory if empty
            if provider_dir:
                self._cleanup_empty_provider_dir(provider_dir)
            
        return success

    def delete_all_datasets(self) -> bool:
        """
        Delete all downloaded datasets.
        The main data directory is preserved, only dataset directories are removed.
        
        Returns:
            True if all datasets were deleted successfully, False if any deletion failed
        """
        if not self.datasets:
            self.logger.info("No datasets to delete")
            return True
        
        success = True
        provider_dirs = set()
        
        for key, meta in list(self.datasets.items()):
            try:
                if meta.download_path.exists():
                    shutil.rmtree(meta.download_path)
                    self.logger.info(f"Deleted dataset directory: {meta.download_path}")
                
                # Store provider directory for later cleanup
                provider_dirs.add(meta.download_path.parent)
                
                # Remove from metadata
                del self.datasets[key]
                
            except Exception as e:
                self.logger.error(f"Error deleting dataset {key}: {str(e)}")
                success = False
        
        # Save metadata after all deletions
        if success:
            self._save_metadata()
            
            # Clean up empty provider directories
            for provider_dir in provider_dirs:
                self._cleanup_empty_provider_dir(provider_dir)
            
        return success

if __name__ == "__main__":
    try:
        api = MobilityAPI()
        token = api.get_access_token()
        if token:
            print("\nYou can now use this access token in curl commands like this:")
            print(f'curl -H "Authorization: Bearer {token}" https://api.mobilitydatabase.org/v1/gtfs_feeds')
    except Exception as e:
        print(f"Error: {str(e)}")