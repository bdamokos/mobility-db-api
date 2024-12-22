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

## Usage

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

