# Mobility Database API Client

[![PyPI version](https://badge.fury.io/py/mobility-db-api.svg)](https://badge.fury.io/py/mobility-db-api)
[![Tests](https://github.com/bdamokos/mobility-db-api/actions/workflows/tests.yml/badge.svg)](https://github.com/bdamokos/mobility-db-api/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/bdamokos/mobility-db-api/branch/main/graph/badge.svg)](https://codecov.io/gh/bdamokos/mobility-db-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://bdamokos.github.io/mobility-db-api/)

A Python client for downloading GTFS files through the [Mobility Database](https://database.mobilitydata.org/) API.

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

Full documentation is available at [bdamokos.github.io/mobility-db-api](https://bdamokos.github.io/mobility-db-api/), including:

- [Quick Start Guide](https://bdamokos.github.io/mobility-db-api/quickstart/)
- [Examples](https://bdamokos.github.io/mobility-db-api/examples/)
- [API Reference](https://bdamokos.github.io/mobility-db-api/api-reference/client/)
- [Contributing Guide](https://bdamokos.github.io/mobility-db-api/contributing/)

## Development

```bash
# Clone repository
git clone https://github.com/bdamokos/mobility-db-api.git
cd mobility-db-api

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Mobility Database](https://database.mobilitydata.org/) for providing the API

