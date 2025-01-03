# Quickstart Guide

## Installation

```bash
pip install mobility-db-api
```

## Basic Usage

### Initialize the Client

```python
from mobility_db_api import MobilityAPI

# Initialize with default settings
api = MobilityAPI()

# Or specify a custom data directory
api = MobilityAPI(data_dir="my_gtfs_data")
```

### Search for Providers

```python
# Search by country code
providers = api.get_providers_by_country("HU")  # Hungary
for provider in providers:
    print(f"Found provider: {provider['provider']}")

# Search by name
providers = api.get_providers_by_name("BKK")
for provider in providers:
    print(f"Found provider: {provider['provider']}")
```

### Download and Extract Datasets

```python
# Download a dataset
dataset_path = api.download_latest_dataset("mdb-123")
print(f"Dataset extracted to: {dataset_path}")

# Download with forced bounding box calculation
dataset_path = api.download_latest_dataset(
    "mdb-123",
    force_bounding_box_calculation=True  # Force calculation from stops.txt
)

# List downloaded datasets with metadata
datasets = api.list_downloaded_datasets()
for dataset in datasets:
    print(f"\nDataset: {dataset.provider_name}")
    print(f"Provider ID: {dataset.provider_id}")
    print(f"Dataset ID: {dataset.dataset_id}")
    print(f"Download date: {dataset.download_date}")
    
    # Feed validity period
    if dataset.feed_start_date:
        print(f"Valid from {dataset.feed_start_date} to {dataset.feed_end_date}")
    
    # Geographical coverage
    if dataset.minimum_latitude is not None:
        print(f"Coverage area: ({dataset.minimum_latitude}, {dataset.minimum_longitude}) to "
              f"({dataset.maximum_latitude}, {dataset.maximum_longitude})")
```

### Working with External GTFS Files

```python
from mobility_db_api import ExternalGTFSAPI
from pathlib import Path

# Initialize the external GTFS client
api = ExternalGTFSAPI()

# Extract a GTFS file
dataset_path = api.extract_gtfs(Path("gtfs.zip"))

# Extract with custom provider name
dataset_path = api.extract_gtfs(
    Path("gtfs.zip"),
    provider_name="My Transit Agency"
)

# Update an existing dataset
dataset_path = api.extract_gtfs(
    Path("updated.zip"),
    provider_id="ext-1"
)
```

## Features

- Search for GTFS providers by country or name
- Download and extract GTFS datasets
- Track dataset metadata:
  - Feed validity dates from feed_info.txt
  - Geographical bounding box from stops.txt
  - Dataset hashes for version control
- Handle external GTFS files
- Automatic fallback to CSV catalog when API is unavailable

## Geographical Coverage

The package automatically handles geographical coverage information:

- For datasets from the Mobility Database API, it uses the provided bounding box
- For datasets from the CSV catalog, it uses the catalog's bounding box information
- For direct source downloads and external GTFS files, it calculates the bounding box from stops.txt
- If bounding box information is missing from API/CSV, it automatically attempts to calculate it from stops.txt
- You can force recalculation from stops.txt using `force_bounding_box_calculation=True`
- Invalid or missing coordinates are handled gracefully
- Coordinates are validated to be within valid ranges (-90/90 for latitude, -180/180 for longitude)

### Bounding Box Calculation Priority

1. If `force_bounding_box_calculation=True`: Always calculate from stops.txt
2. If using direct source: Always calculate from stops.txt
3. If API/CSV provides bounding box: Use provided values
4. If API/CSV bounding box is missing: Attempt calculation from stops.txt
5. If calculation fails: Return None for all coordinates

## Error Handling

The package includes robust error handling:

- Gracefully handles missing or invalid files
- Falls back to CSV catalog when API is unavailable
- Validates coordinates and other data
- Provides detailed logging for troubleshooting 