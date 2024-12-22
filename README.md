# Mobility Database API Client

[![PyPI version](https://badge.fury.io/py/mobility-db-api.svg)](https://badge.fury.io/py/mobility-db-api)
[![Tests](https://github.com/bdamokos/mobility-db-api/actions/workflows/tests.yml/badge.svg)](https://github.com/bdamokos/mobility-db-api/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/bdamokos/mobility-db-api/branch/main/graph/badge.svg)](https://codecov.io/gh/bdamokos/mobility-db-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python client for downloading GTFS files through the [Mobility Database](https://database.mobilitydata.org/) API.

## Installation

You can install the package from PyPI:

```bash
pip install mobility-db-api
```

Or directly from GitHub:

```bash
pip install git+https://github.com/bdamokos/mobility-db-api.git
```

## Quick Start

First, you need to get a refresh token from the Mobility Database API. You can store it in a `.env` file:

```bash
MOBILITY_API_REFRESH_TOKEN=your_token_here
```

Then you can use the API client:

```python
from mobility_db_api import MobilityAPI

# Initialize the client
api = MobilityAPI()

# Search for providers in Hungary
providers = api.get_providers_by_country("HU")

# Download a dataset
dataset_path = api.download_latest_dataset("tld-5862")  # Volánbusz
```

## Features

- Search providers by country or name
- Download GTFS datasets from hosted or direct sources
- Automatic metadata tracking
- Environment variable support for API tokens
- Progress tracking for downloads
- Feed validity period detection
- Dataset management (listing and deleting datasets)

## API Reference

### Initialization

```python
api = MobilityAPI(data_dir=None, refresh_token=None)
```

- `data_dir`: Optional directory path where datasets will be stored. Defaults to './mobility_datasets'
- `refresh_token`: Optional API refresh token. If not provided, will be read from MOBILITY_API_REFRESH_TOKEN environment variable

### Provider Search

#### Search by Country

```python
providers = api.get_providers_by_country("HU")
```

Returns a list of providers in the specified country. Each provider is a dictionary containing:
- `id`: Provider's unique identifier
- `provider`: Provider's name
- `country`: Provider's country
- `source_info`: Information about data sources

#### Search by Name

```python
providers = api.get_providers_by_name("BKK")
```

Returns a list of providers matching the name (case-insensitive, partial match). The returned format is the same as for country search.

### Dataset Management

#### Download Dataset

```python
dataset_path = api.download_latest_dataset(
    provider_id="tld-5862",
    download_dir=None,
    use_direct_source=False
)
```

Downloads and extracts the latest GTFS dataset from a provider:
- `provider_id`: The unique identifier of the provider
- `download_dir`: Optional custom directory to store the dataset
- `use_direct_source`: Whether to use direct download URL instead of hosted dataset
- Returns: Path to the extracted dataset directory if successful, None if download fails

#### List Downloaded Datasets

```python
datasets = api.list_downloaded_datasets()
```

Returns a list of `DatasetMetadata` objects containing:
- `provider_id`: Provider's unique identifier
- `provider_name`: Provider's name
- `dataset_id`: Dataset's unique identifier
- `download_date`: When the dataset was downloaded
- `source_url`: URL the dataset was downloaded from
- `is_direct_source`: Whether it was a direct download
- `api_provided_hash`: Hash provided by the API (if any)
- `file_hash`: Actual hash of the downloaded file
- `download_path`: Path to the extracted dataset
- `feed_start_date`: Start date of feed validity
- `feed_end_date`: End date of feed validity

#### Delete Dataset

```python
success = api.delete_dataset(
    provider_id="tld-5862",
    dataset_id=None  # Optional
)
```

Deletes a downloaded dataset:
- `provider_id`: The unique identifier of the provider
- `dataset_id`: Optional specific dataset ID. If not provided, deletes the latest dataset
- Returns: True if the dataset was deleted, False if it wasn't found or couldn't be deleted

## Examples

### Basic Usage

```python
from mobility_db_api import MobilityAPI

# Initialize client
api = MobilityAPI()

# Search for providers
hu_providers = api.get_providers_by_country("HU")
bkk_providers = api.get_providers_by_name("BKK")

# Download latest dataset
dataset_path = api.download_latest_dataset("tld-5862")
```

### Dataset Management

```python
from mobility_db_api import MobilityAPI

api = MobilityAPI()

# List all downloaded datasets
datasets = api.list_downloaded_datasets()
for dataset in datasets:
    print(f"Provider: {dataset.provider_name}")
    print(f"Dataset ID: {dataset.dataset_id}")
    print(f"Downloaded: {dataset.download_date}")
    print(f"Location: {dataset.download_path}")
    print()

# Delete a specific dataset
api.delete_dataset("tld-5862")  # Delete latest dataset from Volánbusz
api.delete_dataset("tld-5862", "specific_dataset_id")  # Delete specific dataset
```

### Custom Download Directory

```python
from mobility_db_api import MobilityAPI
from pathlib import Path

# Use custom directory for all downloads
api = MobilityAPI(data_dir="custom_downloads")

# Use custom directory for specific download
dataset_path = api.download_latest_dataset(
    provider_id="tld-5862",
    download_dir="specific_download"
)
```

## Development

To set up the development environment:

```bash
# Clone the repository
git clone https://github.com/bdamokos/mobility-db-api.git
cd mobility-db-api

# Install in development mode with test dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Mobility Database](https://database.mobilitydata.org/) for providing the API

