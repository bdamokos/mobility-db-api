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
    """Class to interact with the Mobility Database API"""
    
    def __init__(self, data_dir: str = "data", refresh_token: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            data_dir: Base directory for all GTFS downloads
            refresh_token: Optional refresh token. If not provided, will try to load from .env file
        """
        self.base_url = "https://api.mobilitydatabase.org/v1"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.data_dir / "datasets_metadata.json"
        self.refresh_token = refresh_token
        self._load_metadata()

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
        """Get a new access token using the refresh token"""
        if not self.refresh_token:
            self.refresh_token = os.getenv("MOBILITY_API_REFRESH_TOKEN")
        if not self.refresh_token:
            raise ValueError("No refresh token provided and none found in .env file")
        
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
            print(f"Exception during token request: {str(e)}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with access token for API requests"""
        token = self.get_access_token()
        if not token:
            raise ValueError("Failed to get access token")
        return {"Authorization": f"Bearer {token}"}

    def get_providers_by_country(self, country_code: str) -> List[Dict]:
        """Get all providers from a specific country"""
        url = f"{self.base_url}/gtfs_feeds"
        params = {"country_code": country_code.upper()}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []

    def get_providers_by_name(self, name: str) -> List[Dict]:
        """Get providers matching a name (case-insensitive partial match)"""
        url = f"{self.base_url}/gtfs_feeds"
        params = {"provider": name}
        
        response = requests.get(url, headers=self._get_headers(), params=params)
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
        """
        Download and extract the latest dataset for a provider.
        
        Args:
            provider_id: The ID of the provider
            download_dir: Optional specific directory for this download. If not provided, uses the base data_dir
            use_direct_source: If True, use the provider's direct URL instead of the hosted one
        
        Returns:
            Path to the extracted dataset directory if successful, None otherwise
        """
        try:
            # Get provider info
            print(f"\nFetching provider info for {provider_id}...")
            url = f"{self.base_url}/gtfs_feeds/{provider_id}"
            response = requests.get(url, headers=self._get_headers())
            if response.status_code != 200:
                print(f"Failed to get provider info: {response.status_code}")
                return None
            
            provider_data = response.json()
            provider_name = provider_data.get('provider', 'Unknown Provider')
            latest_dataset = provider_data.get('latest_dataset')
            
            # For direct source, we don't need latest_dataset
            if use_direct_source:
                if not provider_data.get('source_info', {}).get('producer_url'):
                    print("No direct download URL available for this provider")
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
                    print(f"No latest dataset available for provider {provider_id}")
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
                        print(f"Dataset {dataset_key} already exists and hash matches")
                        return existing.download_path
                    elif not api_hash and existing.download_path.exists():
                        # For direct source, download and compare file hash
                        print("Checking if direct source dataset has changed...")
                        temp_file = provider_dir / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                        start_time = time.time()
                        response = requests.get(download_url)
                        download_time = time.time() - start_time
                        if response.status_code == 200:
                            with open(temp_file, 'wb') as f:
                                f.write(response.content)
                            new_hash = self._calculate_file_hash(temp_file)
                            if new_hash == existing.file_hash:
                                temp_file.unlink()
                                print(f"Dataset {dataset_key} already exists and content matches")
                                return existing.download_path
                            # If hash different, continue with new download
                            temp_file.unlink()
            
            # Download dataset
            print(f"\nDownloading dataset from {download_url}...")
            start_time = time.time()
            response = requests.get(download_url)
            download_time = time.time() - start_time
            
            if response.status_code != 200:
                print(f"Failed to download dataset: {response.status_code}")
                return None
            
            # Save and process the zip file
            zip_file = provider_dir / f"{latest_dataset['id']}.zip"
            with open(zip_file, 'wb') as f:
                f.write(response.content)
            
            zip_size = zip_file.stat().st_size
            print(f"Download completed in {download_time:.2f} seconds")
            print(f"Downloaded file size: {zip_size / 1024 / 1024:.2f} MB")
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(zip_file)
            
            # Extract dataset
            print("\nExtracting dataset...")
            extract_dir = provider_dir / latest_dataset['id']
            start_time = time.time()
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            extract_time = time.time() - start_time
            
            extracted_size = self._get_directory_size(extract_dir)
            print(f"Extraction completed in {extract_time:.2f} seconds")
            print(f"Extracted size: {extracted_size / 1024 / 1024:.2f} MB")
            
            # Get feed dates from feed_info.txt
            feed_start_date, feed_end_date = self._get_feed_dates(extract_dir)
            if feed_start_date and feed_end_date:
                print(f"Feed validity period: {feed_start_date} to {feed_end_date}")
            
            # Clean up zip file
            print("Cleaning up downloaded zip file...")
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
            print(f"Network error during download: {str(e)}")
            return None
        except (zipfile.BadZipFile, OSError) as e:
            print(f"Error processing dataset: {str(e)}")
            return None

    def list_downloaded_datasets(self) -> List[DatasetMetadata]:
        """
        Get a list of all downloaded datasets in the data directory.
        
        Returns:
            List of DatasetMetadata objects for all downloaded datasets
        """
        return [meta for meta in self.datasets.values() 
                if meta.download_path.exists()]

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
            print(f"No matching dataset found for provider {provider_id}")
            return False
        
        # If dataset_id not specified, take the latest one
        if dataset_id is None and len(matches) > 1:
            matches.sort(key=lambda x: x[1].download_date, reverse=True)
        
        key, meta = matches[0]
        
        try:
            if meta.download_path.exists():
                shutil.rmtree(meta.download_path)
                print(f"Deleted dataset directory: {meta.download_path}")
            
            # Remove from metadata
            del self.datasets[key]
            self._save_metadata()
            
            return True
            
        except Exception as e:
            print(f"Error deleting dataset: {str(e)}")
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