from pathlib import Path
from typing import Optional, List
from datetime import datetime
import csv
import zipfile
import shutil
from .api import MobilityAPI, DatasetMetadata
from .utils import calculate_bounding_box
import json


class ExternalGTFSAPI(MobilityAPI):
    """Extension of MobilityAPI for handling external GTFS files not in the Mobility Database.
    
    This class provides functionality to:
    - Extract and process external GTFS ZIP files
    - Generate unique provider IDs for external sources
    - Extract agency names from GTFS files
    - Handle versioning of datasets
    - Match files to existing providers
    
    Example:
        >>> api = ExternalGTFSAPI()
        >>> # Extract with automatic provider ID and name from agency.txt
        >>> dataset_path = api.extract_gtfs(Path("gtfs.zip"))
        >>> # Extract with specific provider name
        >>> dataset_path = api.extract_gtfs(
        ...     Path("gtfs.zip"),
        ...     provider_name="My Transit Agency"
        ... )
        >>> # Update existing provider's dataset
        >>> dataset_path = api.extract_gtfs(
        ...     Path("updated.zip"),
        ...     provider_id="ext-1"
        ... )
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._external_provider_counter_file = self.data_dir / ".external_provider_counter"
        self._initialize_counter()

    def _initialize_counter(self):
        """Initialize or read the external provider counter."""
        if not self._external_provider_counter_file.exists():
            self._external_provider_counter_file.write_text("1")
        
    def _get_next_provider_id(self) -> str:
        """Get the next available external provider ID."""
        with self._external_provider_counter_file.open("r+") as f:
            counter = int(f.read().strip())
            f.seek(0)
            f.write(str(counter + 1))
            f.truncate()
        return f"ext-{counter}"

    def _get_agency_names(self, extract_dir: Path) -> List[str]:
        """
        Extract agency names from agency.txt if available.
        Returns a list of agency names since a GTFS feed can contain multiple agencies.
        """
        agency_file = extract_dir / "agency.txt"
        if not agency_file.exists():
            return []

        try:
            agency_names = []
            with open(agency_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "agency_name" in row:
                        agency_names.append(row["agency_name"])
            return agency_names
        except (StopIteration, KeyError, csv.Error):
            return []

    def _find_provider_by_hash_and_name(
        self, file_hash: str, provider_name: Optional[str]
    ) -> Optional[str]:
        """
        Find a provider ID by file hash and optionally provider name.
        If provider_name is provided, requires both hash and name to match.
        """
        for key, meta in self.datasets.items():
            if provider_name is not None:
                # If provider name is provided, only match by name
                if meta.provider_name == provider_name:
                    return meta.provider_id
            else:
                # If no provider name is provided, match by hash
                if meta.file_hash == file_hash:
                    return meta.provider_id
        return None

    def extract_gtfs(
        self,
        zip_path: Path,
        provider_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        download_dir: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Extract and process an external GTFS ZIP file.

        Args:
            zip_path: Path to the GTFS ZIP file
            provider_id: Optional provider ID to use. If not provided, will generate one
                       or reuse existing if the same file was processed before
            provider_name: Optional provider name. If not provided, will extract
                         from agency.txt. If multiple agencies exist, names will be
                         combined with commas
            download_dir: Optional custom directory to store the dataset

        Returns:
            Path to the extracted dataset directory if successful, None if extraction fails
        """
        try:
            # Calculate file hash
            file_hash = self._calculate_file_hash(zip_path)

            # Try to find existing provider by name or generate new ID
            if not provider_id:
                if provider_name:
                    # If provider name is provided, look for exact match by name only
                    for key, meta in self.datasets.items():
                        if meta.provider_name == provider_name:
                            provider_id = meta.provider_id
                            self.logger.info(f"Found existing provider ID {provider_id} for name {provider_name}")
                            break
                    # If no match found by name, generate new ID
                    if not provider_id:
                        provider_id = self._get_next_provider_id()
                        self.logger.info(f"Generated new provider ID {provider_id} for name {provider_name}")
                else:
                    # Only do hash matching if no provider name is provided
                    for key, meta in self.datasets.items():
                        if meta.file_hash == file_hash:
                            provider_id = meta.provider_id
                            provider_name = meta.provider_name  # Use the name from the matching dataset
                            break
                    # If no match found by hash, generate new ID
                    if not provider_id:
                        provider_id = self._get_next_provider_id()

            # Create a temporary directory for extraction
            base_dir = Path(download_dir) if download_dir else self.data_dir
            base_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = base_dir / f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            temp_dir.mkdir()

            # Extract ZIP to get agency name if needed
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile as e:
                self.logger.error(f"Invalid ZIP file: {str(e)}")
                shutil.rmtree(temp_dir)
                return None

            # Get provider name from agency.txt if not provided
            if not provider_name:
                agency_names = self._get_agency_names(temp_dir)
                provider_name = ", ".join(agency_names) if agency_names else "Unknown Provider"

            # Create provider directory
            safe_name = self._sanitize_provider_name(provider_name)
            provider_dir = base_dir / f"{provider_id}_{safe_name}"
            provider_dir.mkdir(exist_ok=True)

            # Find old dataset for this provider/name combination
            old_dataset_path = None
            old_key = None
            for key, meta in list(self.datasets.items()):
                if meta.provider_id == provider_id and meta.provider_name == provider_name:
                    old_dataset_path = meta.download_path
                    old_key = key
                    self.logger.info(f"Found old dataset {key} for provider {provider_id} ({provider_name})")
                    break  # Only remove the first match

            # Generate dataset ID using timestamp and counter if needed
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            dataset_id = f"direct_{timestamp}"
            counter = 1
            while any(meta.dataset_id == dataset_id for meta in self.datasets.values()):
                dataset_id = f"direct_{timestamp}_{counter}"
                counter += 1
            dataset_dir = provider_dir / dataset_id

            # Move extracted contents to final location
            if dataset_dir.exists():
                shutil.rmtree(dataset_dir)
            shutil.move(temp_dir, dataset_dir)

            # Get feed dates
            feed_start_date, feed_end_date = self._get_feed_dates(dataset_dir)

            # Calculate bounding box
            min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(dataset_dir)

            # Create metadata
            metadata = DatasetMetadata(
                provider_id=provider_id,
                provider_name=provider_name,
                dataset_id=dataset_id,
                download_date=datetime.now(),
                source_url=str(zip_path),
                is_direct_source=True,
                api_provided_hash=None,
                file_hash=file_hash,
                download_path=dataset_dir,
                feed_start_date=feed_start_date,
                feed_end_date=feed_end_date,
                minimum_latitude=min_lat,
                maximum_latitude=max_lat,
                minimum_longitude=min_lon,
                maximum_longitude=max_lon,
            )

            # Add new dataset
            dataset_key = f"{provider_id}_{dataset_id}"
            self.datasets[dataset_key] = metadata
            self.logger.info(f"Added new dataset {dataset_key} for provider {provider_id} ({provider_name})")

            # Clean up old dataset if it exists
            if old_dataset_path and old_dataset_path.exists() and old_key:
                self.logger.info(f"Cleaning up old dataset at {old_dataset_path}")
                cleanup_success = False
                try:
                    # Clean up the old dataset
                    shutil.rmtree(old_dataset_path)
                    # Only remove old dataset from metadata if cleanup was successful
                    del self.datasets[old_key]
                    cleanup_success = True
                    self.logger.info(f"Successfully cleaned up old dataset {old_key}")
                except Exception as e:
                    self.logger.error(f"Failed to clean up old dataset: {str(e)}")
                    # If cleanup failed, remove the new dataset from metadata
                    if dataset_key in self.datasets:
                        del self.datasets[dataset_key]
                        return None

            # Save metadata once at the end
            if download_dir:
                self._save_metadata(base_dir)
            else:
                self._save_metadata()

            # Log final state
            self.logger.info(f"Final datasets: {list(self.datasets.keys())}")
            return dataset_dir

        except Exception as e:
            self.logger.error(f"Error processing GTFS file: {str(e)}")
            if "temp_dir" in locals() and temp_dir.exists():
                shutil.rmtree(temp_dir)
            return None 