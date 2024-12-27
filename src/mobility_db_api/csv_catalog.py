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
            response = requests.get(self.CATALOG_URL, allow_redirects=True)
            if response.status_code == 200:
                with open(self.csv_path, "wb") as f:
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
            List of provider dictionaries with standardized fields matching the API format.
        """
        if not self._download_csv(force=force_download):
            return []

        providers = []
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip inactive or deprecated providers
                    if row.get("status") in ("inactive", "deprecated"):
                        continue

                    # Skip redirected providers
                    if row.get("redirect.id"):
                        continue

                    provider = {
                        "id": f"mdb-{row.get('mdb_source_id', '')}",
                        "data_type": row.get("data_type", "gtfs"),
                        "status": row.get("status", ""),
                        "created_at": row.get("created_at", ""),
                        "external_ids": [
                            {
                                "external_id": row.get("mdb_source_id", ""),
                                "source": "mdb",
                            }
                        ],
                        "provider": row.get("provider", "Unknown Provider"),
                        "feed_name": row.get("feed_name", ""),
                        "note": row.get("note", ""),
                        "feed_contact_email": row.get("feed_contact_email", ""),
                        "source_info": {
                            "producer_url": row.get("urls.direct_download", ""),
                            "authentication_type": int(
                                row.get("urls.authentication_type", "0") or "0"
                            ),
                            "authentication_info_url": row.get(
                                "urls.authentication_info", ""
                            ),
                            "api_key_parameter_name": row.get(
                                "urls.api_key_parameter_name", ""
                            ),
                            "license_url": row.get("urls.license", ""),
                        },
                        "locations": [
                            {
                                "country_code": row.get("location.country_code", ""),
                                "country": row.get("location.country", ""),
                                "subdivision_name": row.get(
                                    "location.subdivision_name"
                                ),
                                "municipality": row.get("location.municipality"),
                            }
                        ],
                        "latest_dataset": {
                            "id": f"mdb-{row.get('mdb_source_id', '')}-{datetime.now().strftime('%Y%m%d%H%M')}",
                            "hosted_url": row.get("urls.latest", ""),
                            "bounding_box": row.get("bounding_box"),
                            "downloaded_at": row.get("downloaded_at"),
                            "hash": row.get("hash"),
                            "validation_report": row.get("validation_report"),
                        },
                    }

                    # Only include GTFS providers that are not inactive/deprecated
                    if provider["data_type"] == "gtfs" and provider["status"] not in (
                        "inactive",
                        "deprecated",
                    ):
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
        return [
            p
            for p in providers
            if any(
                loc["country_code"].upper() == country_code.upper()
                for loc in p["locations"]
            )
        ]

    def get_providers_by_name(self, name: str) -> List[Dict]:
        """Search for providers by name.

        Args:
            name: Provider name to search for (case-insensitive partial match)

        Returns:
            List of matching provider dictionaries.
        """
        providers = self.get_providers()
        name_lower = name.lower()
        return [p for p in providers if name_lower in p["provider"].lower()]

    def _normalize_provider_id(self, provider_id: str) -> str:
        """Normalize provider ID to match CSV catalog format.

        Handles the following formats:
        - "123" -> "123"
        - "mdb-123" -> "123"
        - "test-123" -> "test-123"
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
            The dictionary includes all provider fields in the standardized format.
        """
        normalized_id = self._normalize_provider_id(provider_id)
        providers = self.get_providers()

        # Try to find the provider by comparing normalized IDs
        for provider in providers:
            if self._normalize_provider_id(provider["id"]) == normalized_id:
                # Check if this is a redirected provider
                if provider.get("redirects"):
                    return None
                return provider

        return None
