# Examples

## Provider Search

```python
from mobility_db_api import MobilityAPI

api = MobilityAPI()

# Search by country (traditional way)
providers = api.get_providers_by_country("BE")
print(f"Found {len(providers)} providers in Belgium")

# Search by name (traditional way)
sncb = api.get_providers_by_name("SNCB")
print(f"Found {len(sncb)} SNCB providers")

# Get provider by ID (new way)
provider = api.get_provider_by_id("mdb-123")
if provider:
    print(f"Found provider: {provider['provider']}")

# Combined search functionality (new way)
# Search by country
be_providers = api.get_provider_info(country_code="BE")
print(f"Found {len(be_providers)} providers in Belgium")

# Search by name
sncb = api.get_provider_info(name="SNCB")
print(f"Found {len(sncb)} SNCB providers")

# Get by ID with downloaded dataset info
provider = api.get_provider_info(provider_id="mdb-123")
if provider:
    print(f"Provider: {provider['provider']}")
    if 'downloaded_dataset' in provider:
        print(f"Downloaded dataset: {provider['downloaded_dataset']['download_path']}")
```

## Dataset Download

```python
from mobility_db_api import MobilityAPI
from pathlib import Path

api = MobilityAPI()

# Download to default location
dataset_path = api.download_latest_dataset("tld-5862")  # Volánbusz ID
print(f"Dataset downloaded to: {dataset_path}")

# Download to custom directory with direct source
dataset_path = api.download_latest_dataset(
    provider_id="tld-5862",
    download_dir="custom_downloads",
    use_direct_source=True
)
```

## Metadata Management

```python
from mobility_db_api import MobilityAPI
from pathlib import Path
import json

api = MobilityAPI()

# Read metadata
metadata_file = Path('downloads/datasets_metadata.json')
if metadata_file.exists():
    with open(metadata_file) as f:
        metadata = json.load(f)
        for dataset_id, info in metadata.items():
            print(f"\nDataset: {dataset_id}")
            print(f"Provider: {info['provider_name']}")
            print(f"Downloaded: {info['download_date']}")
```

## Concurrent Downloads

```python
from mobility_db_api import MobilityAPI
from concurrent.futures import ThreadPoolExecutor

def download_dataset(provider_id: str) -> str:
    """Download dataset in a separate thread"""
    api = MobilityAPI()  # Each thread gets its own instance
    try:
        path = api.download_latest_dataset(provider_id)
        return f"Successfully downloaded to {path}"
    except Exception as e:
        return f"Failed to download: {e}"

# Download multiple datasets concurrently
api = MobilityAPI()
providers = api.get_providers_by_country("BE")
provider_ids = [p['id'] for p in providers[:3]]  # First 3 providers

with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(download_dataset, provider_ids))

for result in results:
    print(result)
```

## Error Handling

```python
from mobility_db_api import MobilityAPI
from mobility_db_api.exceptions import (
    AuthenticationError,
    DownloadError,
    MetadataError
)

api = MobilityAPI()

try:
    dataset_path = api.download_latest_dataset("invalid-id")
except AuthenticationError:
    print("Check your API token")
except DownloadError as e:
    print(f"Download failed: {e}")
except MetadataError as e:
    print(f"Metadata error: {e}")
```

## External GTFS Files

```python
from mobility_db_api import ExternalGTFSAPI
from pathlib import Path

# Initialize API
api = ExternalGTFSAPI()

# Extract GTFS with automatic provider ID and name from agency.txt
dataset_path = api.extract_gtfs(
    zip_path=Path("gtfs_files/agency1.zip")
)

# Extract with specific provider name
dataset_path = api.extract_gtfs(
    zip_path=Path("gtfs_files/agency2.zip"),
    provider_name="My Transit Agency"
)

# Update existing provider's dataset
dataset_path = api.extract_gtfs(
    zip_path=Path("gtfs_files/agency1_updated.zip"),
    provider_id="ext-1"  # Use an existing provider ID
)

# Extract to custom directory
dataset_path = api.extract_gtfs(
    zip_path=Path("gtfs_files/agency3.zip"),
    download_dir="custom_downloads"
)

# List all datasets (including external ones)
datasets = api.list_downloaded_datasets()
for dataset in datasets:
    print(f"Provider: {dataset.provider_name} ({dataset.provider_id})")
    print(f"Dataset: {dataset.dataset_id}")
    print(f"Path: {dataset.download_path}")
```

The `ExternalGTFSAPI` class extends `MobilityAPI` to handle GTFS files not in the Mobility Database. Key features:

- Automatic provider ID generation with `ext-` prefix
- Agency name extraction from agency.txt (supports multiple agencies)
- Smart file matching based on content hash
- Versioning support with automatic cleanup of old datasets
- All base class methods (list, delete, etc.) work with external datasets

For more examples, see [examples/external_gtfs_example.py](examples/external_gtfs_example.py). 