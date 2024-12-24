# API Reference: Client

::: mobility_db_api.api.MobilityAPI
    handler: python
    options:
        show_root_heading: true
        show_source: true
        heading_level: 2

## Common Exceptions

The client can raise the following exceptions:

### ValueError

Raised in cases like:
- Missing or invalid refresh token
- Failed token refresh
- Invalid provider ID

### requests.exceptions.RequestException

Raised for network-related issues:
- Connection errors
- API errors
- Timeout issues

### OSError

Raised for file system issues:
- Permission errors
- Disk space issues
- File access problems

## Environment Variables

The following environment variables can be used to configure the client:

- `MOBILITY_API_REFRESH_TOKEN`: The API refresh token for authentication
- `MOBILITY_API_BASE_URL`: The base URL of the Mobility Database API
- `MOBILITY_API_DATA_DIR`: The default directory for storing downloaded datasets

## Type Hints

```python
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

@dataclass
class DatasetMetadata:
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

# Function signatures
def get_providers_by_country(country_code: str) -> List[Dict]: ...
def get_providers_by_name(name: str) -> List[Dict]: ...
def download_latest_dataset(
    provider_id: str,
    download_dir: Optional[str] = None,
    use_direct_source: bool = False
) -> Optional[Path]: ...
def list_downloaded_datasets() -> List[DatasetMetadata]: ...
def delete_dataset(provider_id: str, dataset_id: Optional[str] = None) -> bool: ...
def delete_provider_datasets(provider_id: str) -> bool: ...
def delete_all_datasets() -> bool: ...
```

## Usage Examples

### Basic Usage

```python
from mobility_db_api import MobilityAPI

# Initialize client
api = MobilityAPI()

# Search for providers
providers = api.get_providers_by_country("BE")
for provider in providers:
    print(f"Found provider: {provider['provider']}")

# Download dataset
dataset_path = api.download_latest_dataset(providers[0]['id'])
print(f"Dataset downloaded to: {dataset_path}")
```

### Dataset Management

```python
from mobility_db_api import MobilityAPI

api = MobilityAPI()

# List downloaded datasets
datasets = api.list_downloaded_datasets()
for dataset in datasets:
    print(f"Dataset: {dataset.dataset_id}")
    print(f"Provider: {dataset.provider_name}")
    print(f"Downloaded: {dataset.download_date}")

# Delete specific dataset
api.delete_dataset("tld-5862", "20240315")

# Delete all datasets for a provider
api.delete_provider_datasets("tld-5862")

# Delete all datasets
api.delete_all_datasets()
```

### Error Handling

```python
from mobility_db_api import MobilityAPI
import requests

api = MobilityAPI()

try:
    dataset_path = api.download_latest_dataset("invalid-id")
except ValueError as e:
    print(f"Invalid input: {e}")
except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
except OSError as e:
    print(f"File system error: {e}")
```

## Implementation Details

### Authentication Flow

1. Initialize client with refresh token
2. Client automatically handles token refresh
3. Access token is used for API requests
4. Refresh token is used to obtain new access tokens

### Download Process

1. Get provider information
2. Choose download source (hosted or direct)
3. Download dataset to specified directory
4. Update metadata with download information
5. Return path to downloaded dataset

### Metadata Management

1. Each download directory has its own metadata file
2. Metadata is locked during updates
3. Changes are detected using checksums
4. Failed downloads are cleaned up 