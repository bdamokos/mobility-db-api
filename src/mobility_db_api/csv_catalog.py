"""CSV catalog functionality for the Mobility Database API client."""

import csv
import requests
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import tempfile
import hashlib

class CSVCatalog:
    """Handler for the Mobility Database CSV catalog."""
    
    CATALOG_URL = "https://share.mobilitydata.org/catalogs-csv"
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the CSV catalog handler.
        
        Args:
            cache_dir: Optional directory for caching the CSV file.
                      If not provided, will use a temporary directory.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir())
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.cache_dir / "mobility_catalog.csv"
        self._providers: Optional[List[Dict]] = None
    
    def _download_csv(self, force: bool = False) -> bool:
        """Download the CSV catalog.
        
        Args:
            force: If True, download even if the file exists.
        
        Returns:
            bool: True if download was successful, False otherwise.
        """
        if not force and self.csv_path.exists():
            return True
            
        try:
            response = requests.get(self.CATALOG_URL)
            if response.status_code == 200:
                with open(self.csv_path, 'wb') as f:
                    f.write(response.content)
                return True
            return False
        except requests.RequestException:
            return False
    
    def _load_providers(self, force_download: bool = False) -> List[Dict]:
        """Load and parse the CSV catalog.
        
        Args:
            force_download: If True, force a new download of the CSV file.
        
        Returns:
            List of provider dictionaries with standardized fields.
        """
        if not self._download_csv(force=force_download):
            return []
        
        providers = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip inactive or deprecated providers
                    if row.get('status') in ('inactive', 'deprecated'):
                        continue
                    
                    # Handle redirects
                    if row.get('redirect.id'):
                        continue  # Skip redirected entries
                    
                    provider = {
                        'id': row.get('mdb_source_id', ''),
                        'provider': row.get('provider', 'Unknown Provider'),
                        'country': row.get('location.country_code', ''),
                        'source_info': {
                            'producer_url': row.get('urls.direct_download', '')
                        },
                        'latest_dataset': {
                            'id': f"csv_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            'hosted_url': row.get('urls.latest', ''),
                            'hash': None  # CSV doesn't provide hashes
                        },
                        'data_type': row.get('data_type', ''),
                        'status': row.get('status', ''),
                        'features': row.get('features', ''),
                        'license_url': row.get('urls.license', '')
                    }
                    
                    # Only include GTFS providers that are not inactive/deprecated
                    if provider['data_type'] == 'gtfs' and provider['status'] not in ('inactive', 'deprecated'):
                        providers.append(provider)
        except (csv.Error, KeyError, UnicodeDecodeError):
            return []
        
        return providers
    
    def get_providers(self, force_reload: bool = False) -> List[Dict]:
        """Get all providers from the CSV catalog.
        
        Args:
            force_reload: If True, force a reload of the CSV file.
        
        Returns:
            List of provider dictionaries.
        """
        if self._providers is None or force_reload:
            self._providers = self._load_providers(force_download=force_reload)
        return self._providers
    
    def get_providers_by_country(self, country_code: str) -> List[Dict]:
        """Search for providers by country code.
        
        Args:
            country_code: Two-letter ISO country code (e.g., "HU" for Hungary)
        
        Returns:
            List of matching provider dictionaries.
        """
        providers = self.get_providers()
        return [p for p in providers if p['country'].upper() == country_code.upper()]
    
    def get_providers_by_name(self, name: str) -> List[Dict]:
        """Search for providers by name.
        
        Args:
            name: Provider name to search for (case-insensitive partial match)
        
        Returns:
            List of matching provider dictionaries.
        """
        providers = self.get_providers()
        name_lower = name.lower()
        return [p for p in providers if name_lower in p['provider'].lower()] 
    
    def _normalize_provider_id(self, provider_id: str) -> str:
        """Normalize provider ID to match CSV catalog format.
        
        Handles the following formats:
        - "123" -> "123"
        - "mdb-123" -> "123"
        - Other formats (e.g., "tld-123") -> unchanged
        
        Args:
            provider_id: The provider ID to normalize
            
        Returns:
            Normalized provider ID for CSV catalog lookup
        """
        if provider_id.startswith("mdb-"):
            return provider_id[4:]  # Remove "mdb-" prefix
        if provider_id.isdigit():
            return provider_id
        return provider_id

    def get_provider_info(self, provider_id: str) -> Optional[Dict]:
        """Get information about a specific provider.
        
        Args:
            provider_id: The unique identifier of the provider.
                       Supports formats: "123", "mdb-123", or other prefixes.
        
        Returns:
            Provider information dictionary if found, None otherwise.
            The dictionary includes standardized fields matching the API response format:
                - provider: Provider name
                - source_info: Source information including direct download URL
                - latest_dataset: Latest dataset information
                - data_type: Type of data (e.g., 'gtfs')
                - status: Provider status
                - features: Provider features
                - license_url: URL to the license information
        """
        normalized_id = self._normalize_provider_id(provider_id)
        providers = self.get_providers()
        provider = next((p for p in providers if p['id'] == normalized_id), None)
        
        if provider:
            return {
                'provider': provider['provider'],
                'source_info': provider['source_info'],
                'latest_dataset': provider['latest_dataset'],
                'data_type': provider['data_type'],
                'status': provider['status'],
                'features': provider['features'],
                'license_url': provider['license_url']
            }
        return None 