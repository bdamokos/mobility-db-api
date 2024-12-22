import os
import requests
import json
import hashlib
import csv
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import zipfile
from unidecode import unidecode
from dotenv import load_dotenv
import shutil
from .logger import setup_logger

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

class MobilityAPI:
    """A client for interacting with the Mobility Database API.

    This class provides methods to search for GTFS providers, download datasets,
    and manage downloaded data. It handles authentication, caching, and metadata
    tracking automatically.

    Attributes:
        data_dir (Path): Directory where downloaded datasets are stored
        refresh_token (str): Token used for API authentication
        datasets (Dict): Dictionary of downloaded dataset metadata
        session (requests.Session): Session object for making HTTP requests

    Example:
        >>> api = MobilityAPI()
        >>> providers = api.get_providers_by_country("HU")
        >>> dataset_path = api.download_latest_dataset("tld-5862")
    """
    
    def __init__(self, data_dir: Optional[str] = None, refresh_token: Optional[str] = None, 
                 log_level: str = "INFO", logger_name: str = "mobility_db_api"):
        """Initialize the MobilityAPI client.

        Args:
            data_dir: Optional directory path where datasets will be stored.
                     Defaults to './mobility_datasets'.
            refresh_token: Optional API refresh token. If not provided, will be read
                         from MOBILITY_API_REFRESH_TOKEN environment variable.
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
            logger_name: Name for the logger instance. Defaults to 'mobility_db_api'.

        Raises:
            ValueError: If no refresh token is provided and none is found in environment.
        """
        # Set up logger
        self.logger = setup_logger(name=logger_name, level=log_level)
        self.logger.debug("Initializing MobilityAPI client")

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "mobility-db-api/0.1.1",
            "Accept": "application/json"
        })
        self.logger.debug("Initialized HTTP session")

        self.base_url = "https://api.mobilitydatabase.org/v1"
        self.data_dir = Path(data_dir) if data_dir else Path("./mobility_datasets")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.data_dir / "datasets_metadata.json"
        self.refresh_token = refresh_token
        self._load_metadata()
        
        self.logger.info(f"Initialized client with data directory: {self.data_dir}")

    def __del__(self):
        """Cleanup method to ensure session is closed"""
        if hasattr(self, 'session'):
            self.session.close()
            self.logger.debug("Closed HTTP session")

    def _get_metadata_file(self, base_dir: Optional[Path] = None) -> Path:
        """Get the appropriate metadata file path based on the base directory"""
        if base_dir is None:
            return self.metadata_file
        return base_dir / "datasets_metadata.json"

    def _load_metadata(self):
        """Load existing metadata from file"""
        self.datasets: Dict[str, DatasetMetadata] = {}
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
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

    def _save_metadata(self, base_dir: Optional[Path] = None):
        """
        Save current metadata to file.
        If base_dir is provided, saves metadata to that directory instead of the default.
        """
        metadata_file = self._get_metadata_file(base_dir)
        
        # Filter datasets to only include those in the target directory
        target_datasets = {
            key: meta for key, meta in self.datasets.items()
            if base_dir is None or str(meta.download_path).startswith(str(base_dir))
        }
        
        data = {
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
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(data, f, indent=2)

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token for API authentication.

        This method handles token refresh automatically when needed. It uses the
        refresh token to obtain a new access token from the API.

        Returns:
            A valid access token string if successful, None if token refresh fails.

        Example:
            >>> api = MobilityAPI()
            >>> token = api.get_access_token()
            >>> print(token)
            'eyJ0eXAiOiJKV1QiLCJhbGc...'
        """
        if not self.refresh_token:
            self.refresh_token = os.getenv("MOBILITY_API_REFRESH_TOKEN")
        if not self.refresh_token:
            raise ValueError("No refresh token provided and none found in .env file")
        
        url = f"{self.base_url}/tokens"
        headers = {"Content-Type": "application/json"}
        data = {"refresh_token": self.refresh_token}
        
        try:
            # Don't use session for token request to avoid authorization header
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    # Update session headers with new token
                    self.session.headers.update({"Authorization": f"Bearer {token}"})
                    self.logger.debug("Updated session with new access token")
                return token
            return None
        except Exception as e:
            self.logger.error(f"Exception during token request: {str(e)}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with access token for API requests"""
        token = self.get_access_token()
        if not token:
            raise ValueError("Failed to get access token")
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
        # Ensure we have a valid token
        self.get_access_token()
        
        url = f"{self.base_url}/gtfs_feeds"
        params = {"country_code": country_code.upper()}
        
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []

    def get_providers_by_name(self, name: str) -> List[Dict]:
        """Search for GTFS providers by name.

        The search is case-insensitive and matches partial names.

        Args:
            name: Provider name or part of the name to search for

        Returns:
            List of provider dictionaries containing provider information.
            Each dictionary includes:
                - id: Provider's unique identifier
                - provider: Provider's name
                - country: Provider's country
                - source_info: Information about data sources

        Example:
            >>> api = MobilityAPI()
            >>> providers = api.get_providers_by_name("BKK")
            >>> for p in providers:
            ...     print(f"{p['provider']}: {p['id']}")
            'BKK: o-u-dr_bkk'
        """
        # Ensure we have a valid token
        self.get_access_token()
        
        url = f"{self.base_url}/gtfs_feeds"
        params = {"provider": name}
        
        response = self.session.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return []

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
            # Ensure we have a valid token
            self.get_access_token()
            
            # Get provider info
            self.logger.info(f"Fetching provider info for {provider_id}")
            url = f"{self.base_url}/gtfs_feeds/{provider_id}"
            response = self.session.get(url)
            if response.status_code != 200:
                self.logger.error(f"Failed to get provider info: {response.status_code}")
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
            if dataset_key in self.datasets:
                existing = self.datasets[dataset_key]
                if existing.is_direct_source == is_direct:
                    if api_hash and api_hash == existing.api_provided_hash:
                        self.logger.info(f"Dataset {dataset_key} already exists and hash matches")
                        return existing.download_path
                    elif not api_hash and existing.download_path.exists():
                        # For direct source, download and compare file hash
                        self.logger.info("Checking if direct source dataset has changed...")
                        temp_file = provider_dir / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                        start_time = time.time()
                        # Use a new session for direct downloads to avoid auth headers
                        if is_direct:
                            response = requests.get(download_url)
                        else:
                            response = self.session.get(download_url)
                        download_time = time.time() - start_time
                        if response.status_code == 200:
                            with open(temp_file, 'wb') as f:
                                f.write(response.content)
                            new_hash = self._calculate_file_hash(temp_file)
                            if new_hash == existing.file_hash:
                                temp_file.unlink()
                                self.logger.info(f"Dataset {dataset_key} already exists and content matches")
                                return existing.download_path
                            # If hash different, continue with new download
                            temp_file.unlink()
            
            # Download dataset
            self.logger.info(f"Downloading dataset from {download_url}")
            start_time = time.time()
            # Use a new session for direct downloads to avoid auth headers
            if is_direct:
                response = requests.get(download_url)
            else:
                # Ensure token is fresh for hosted downloads
                self.get_access_token()
                response = self.session.get(download_url)
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
            self.logger.debug(f"Downloaded file size: {zip_size / 1024 / 1024:.2f} MB")
            
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
            self.logger.debug(f"Extracted size: {extracted_size / 1024 / 1024:.2f} MB")
            
            # Get feed dates from feed_info.txt
            feed_start_date, feed_end_date = self._get_feed_dates(extract_dir)
            if feed_start_date and feed_end_date:
                self.logger.info(f"Feed validity period: {feed_start_date} to {feed_end_date}")
            
            # Clean up zip file
            self.logger.debug("Cleaning up downloaded zip file")
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
            
            return extract_dir
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during download: {str(e)}")
            return None
        except (zipfile.BadZipFile, OSError) as e:
            self.logger.error(f"Error processing dataset: {str(e)}")
            return None

    def list_downloaded_datasets(self) -> List[DatasetMetadata]:
        """Get a list of all downloaded datasets in the data directory.

        Returns:
            List of DatasetMetadata objects for all downloaded datasets.
            Each object contains:
                - provider_id: Provider's unique identifier
                - provider_name: Provider's name
                - dataset_id: Dataset's unique identifier
                - download_date: When the dataset was downloaded
                - source_url: URL the dataset was downloaded from
                - is_direct_source: Whether it was a direct download
                - api_provided_hash: Hash provided by the API (if any)
                - file_hash: Actual hash of the downloaded file
                - download_path: Path to the extracted dataset
                - feed_start_date: Start date of feed validity
                - feed_end_date: End date of feed validity

        Example:
            >>> api = MobilityAPI()
            >>> datasets = api.list_downloaded_datasets()
            >>> for ds in datasets:
            ...     print(f"{ds.provider_name}: {ds.download_date}")
            'Volánbusz: 2024-03-15 10:30:45'
        """
        return [meta for meta in self.datasets.values() 
                if meta.download_path.exists()]

    def delete_dataset(self, provider_id: str, dataset_id: Optional[str] = None) -> bool:
        """Delete a downloaded dataset.

        If no specific dataset_id is provided, deletes the latest dataset
        from the specified provider.

        Args:
            provider_id: The unique identifier of the provider
            dataset_id: Optional specific dataset ID. If not provided,
                       deletes the latest dataset

        Returns:
            True if the dataset was deleted, False if it wasn't found
            or couldn't be deleted

        Example:
            >>> api = MobilityAPI()
            >>> # Delete latest dataset from Volánbusz
            >>> api.delete_dataset("tld-5862")
            True
            >>> # Delete specific dataset
            >>> api.delete_dataset("tld-5862", "specific_dataset_id")
            True
        """
        # Find matching datasets
        matches = [
            (key, meta) for key, meta in self.datasets.items()
            if meta.provider_id == provider_id and
            (dataset_id is None or meta.dataset_id == dataset_id)
        ]
        
        if not matches:
            self.logger.warning(f"No matching dataset found for provider {provider_id}")
            return False
        
        # If dataset_id not specified, take the latest one
        if dataset_id is None and len(matches) > 1:
            matches.sort(key=lambda x: x[1].download_date, reverse=True)
        
        key, meta = matches[0]
        
        try:
            if meta.download_path.exists():
                shutil.rmtree(meta.download_path)
                self.logger.info(f"Deleted dataset directory: {meta.download_path}")
            
            # Remove from metadata
            del self.datasets[key]
            self._save_metadata()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting dataset: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        api = MobilityAPI()
        token = api.get_access_token()
        if token:
            print("\nYou can now use this access token in curl commands like this:")
            print(f'curl -H "Authorization: Bearer {token}" https://api.mobilitydatabase.org/v1/gtfs_feeds')
    except Exception as e:
        print(f"Error: {str(e)}")