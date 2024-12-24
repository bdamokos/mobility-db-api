# Examples

## Provider Search

```python
from mobility_db_api import MobilityAPI

api = MobilityAPI()

# Search by country
providers = api.get_providers_by_country("BE")
print(f"Found {len(providers)} providers in Belgium")

# Search by name
sncb = api.get_providers_by_name("SNCB")
print(f"Found {len(sncb)} SNCB providers")

# Print provider details
if providers:
    provider = providers[0]
    print(f"Provider: {provider['provider']}")
    print(f"ID: {provider['id']}")
    print(f"Direct download: {'Yes' if provider.get('direct_download_url') else 'No'}")
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