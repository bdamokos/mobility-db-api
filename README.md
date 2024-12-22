# Mobility Database API Explorer

This project provides tools to interact with the [Mobility Database API](https://mobilitydatabase.org) and explore GTFS data from various transit providers. The Mobility Database is a comprehensive repository of public transportation data from around the world, providing standardized GTFS feeds for transit agencies.

## Installation

You can install this package in several ways:

1. From PyPI (recommended):
```bash
pip install mobility-db-api
```

2. From GitHub:
```bash
pip install git+https://github.com/bdamokos/mobility-db-api.git
```

3. For development:
```bash
git clone https://github.com/bdamokos/mobility-db-api.git
cd mobility-db-api
pip install -e .
```

## Authentication

1. Register for an account at [mobilitydatabase.org](https://mobilitydatabase.org)
2. After registration, obtain your refresh token from your account settings
3. Store your refresh token in a `.env` file:
```
MOBILITY_API_REFRESH_TOKEN=your_refresh_token_here
```

## Usage

```python
from mobility_db_api import MobilityAPI

# Initialize with default settings
api = MobilityAPI()

# Or specify custom data directory and token
api = MobilityAPI(data_dir="custom_data", refresh_token="your_token_here")

# Search providers by country
providers = api.get_providers_by_country("HU")  # Hungary

# Search providers by name
providers = api.get_providers_by_name("SNCB")  # Belgian Railways

# Download latest dataset
dataset_path = api.download_latest_dataset(provider_id="tld-5862")

# Download using direct URL (if available)
dataset_path = api.download_latest_dataset(provider_id="tld-5862", use_direct_source=True)
```

## Features

- Search transit providers by country or name
- Download and extract GTFS datasets
- Support for both hosted and direct source downloads
- Automatic handling of dataset updates
- Metadata tracking including feed validity dates
- Custom download locations with separate metadata tracking
- Filesystem-friendly naming with Unicode support

## Data Storage

Downloaded datasets are organized as follows:
- Each provider gets a dedicated directory named `{provider_id}_{sanitized_name}`
- Datasets are extracted to subdirectories with their dataset ID
- Metadata is stored in `datasets_metadata.json` in each data directory
- Original zip files are automatically cleaned up after extraction

