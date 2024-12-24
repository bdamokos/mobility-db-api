# Mobility Database API Client

A Python client for downloading GTFS files through the [Mobility Database](https://database.mobilitydata.org/) API.

[![PyPI version](https://badge.fury.io/py/mobility-db-api.svg)](https://badge.fury.io/py/mobility-db-api)
[![Tests](https://github.com/bdamokos/mobility-db-api/actions/workflows/tests.yml/badge.svg)](https://github.com/bdamokos/mobility-db-api/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/bdamokos/mobility-db-api/branch/main/graph/badge.svg)](https://codecov.io/gh/bdamokos/mobility-db-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Search for GTFS providers by country or name
- Download GTFS datasets from hosted or direct sources
- Track dataset metadata and changes
- Thread-safe and process-safe operations
- Automatic token refresh and error handling

## Installation

```bash
pip install mobility-db-api
```

## Quick Example

```python
from mobility_db_api import MobilityAPI

# Initialize client (uses MOBILITY_API_REFRESH_TOKEN env var)
api = MobilityAPI()

# Search for providers in Belgium
providers = api.get_providers_by_country("BE")
print(f"Found {len(providers)} providers")

# Download a dataset
if providers:
    dataset_path = api.download_latest_dataset(providers[0]['id'])
    print(f"Dataset downloaded to: {dataset_path}")
```

## Documentation

- [Quick Start Guide](quickstart.md) - Get up and running in minutes
- [Examples](examples.md) - Common use cases and patterns
- [API Reference](api-reference/client.md) - Detailed API documentation
- [Contributing](contributing.md) - Help improve the client
- [Changelog](changelog.md) - Latest changes and updates 