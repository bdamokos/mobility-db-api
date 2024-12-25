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

# Client API Reference

## MobilityAPI

The main client class for interacting with the Mobility Database API.

### Constructor

```python
MobilityAPI(data_dir: str = "data", 
           refresh_token: Optional[str] = None,
           log_level: str = "INFO", 
           logger_name: str = "mobility_db_api",
           force_csv_mode: bool = False)
```

Parameters:
- `data_dir`: Base directory for all GTFS downloads (default: "data")
- `refresh_token`: Optional refresh token. If not provided, will try to load from .env file
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO
- `logger_name`: Name for the logger instance. Defaults to 'mobility_db_api'
- `force_csv_mode`: If True, always use CSV catalog even if API key is available

The client can operate in two modes:
1. API mode (default): Uses the Mobility Database API with authentication
2. CSV mode: Uses the CSV catalog when no API key is provided or when force_csv_mode is True

### Operating Modes

#### API Mode
When a valid refresh token is available (either passed directly or through environment variables), the client operates in API mode. This mode provides:
- Full access to all API features
- Real-time dataset information
- Provider search capabilities
- Dataset downloads with hash verification

#### CSV Mode
The client automatically falls back to CSV mode when:
- No API key is available
- Authentication fails
- API requests return errors (e.g., 413 Request Entity Too Large)
- `force_csv_mode=True` is set

CSV mode provides:
- Basic provider information from a local CSV catalog
- Dataset download URLs
- Provider search by country and name
- ID normalization for consistent provider lookup

### ID Normalization

The CSV catalog supports the following ID formats:
- Direct numeric IDs (e.g., "123")
- MDB-prefixed IDs (e.g., "mdb-123")
- Other prefixed IDs are not resolvable (e.g., "tld-123")

### Methods

#### get_providers_by_country
```python
get_providers_by_country(country_code: str) -> List[Dict]
```
Search for GTFS providers by country code.

Parameters:
- `country_code`: Two-letter ISO country code (e.g., "HU" for Hungary)

Returns:
- List of provider dictionaries containing provider information

Example:
```python
api = MobilityAPI()
providers = api.get_providers_by_country("HU")
for p in providers:
    print(f"{p['provider']}: {p['id']}")
```

#### get_providers_by_name
```python
get_providers_by_name(name: str) -> List[Dict]
```
Search for providers by name.

Parameters:
- `name`: Provider name to search for (case-insensitive partial match)

Returns:
- List of matching provider dictionaries

Example:
```python
api = MobilityAPI()
providers = api.get_providers_by_name("BKK")
```

#### download_latest_dataset
```python
download_latest_dataset(provider_id: str, 
                       download_dir: Optional[str] = None,
                       use_direct_source: bool = False) -> Optional[Path]
```
Download the latest GTFS dataset from a provider.

Parameters:
- `provider_id`: The unique identifier of the provider
- `download_dir`: Optional custom directory to store the dataset
- `use_direct_source`: Whether to use direct download URL instead of hosted dataset

Returns:
- Path to the extracted dataset directory if successful, None if download fails

Example:
```python
api = MobilityAPI()
dataset_path = api.download_latest_dataset("mdb-123")
```

### Error Handling

The client includes robust error handling:
- Graceful fallback to CSV mode on API errors
- Automatic retry with CSV catalog on authentication failures
- Clear error messages and logging
- Safe handling of network issues and invalid responses

### Best Practices

1. **Mode Selection**:
   - Use API mode when real-time data is critical
   - Use CSV mode for basic provider information or when API access is not available
   - Consider `force_csv_mode=True` for better performance when only basic features are needed

2. **Error Handling**:
   - Always check return values for None/empty lists
   - Use try/except blocks for network operations
   - Monitor logs for important messages

3. **Resource Management**:
   - Use custom data directories for better organization
   - Clean up downloaded datasets when no longer needed
   - Monitor disk space usage

Example:
```python
# API mode with fallback
api = MobilityAPI()
providers = api.get_providers_by_country("HU")

# Force CSV mode for better performance
api_csv = MobilityAPI(force_csv_mode=True)
providers = api_csv.get_providers_by_country("HU")

# Custom data directory
api = MobilityAPI(data_dir="custom/path")
dataset = api.download_latest_dataset("mdb-123")
``` 