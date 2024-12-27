# Quick Start

## Installation

```bash
pip install mobility-db-api
```

## Authentication (Optional)

The client works in two modes:
1. CSV mode (default): Uses a local CSV catalog with basic provider information
2. API mode: Provides real-time, complete dataset information when an API token is available

To enable API mode:
1. Get your API token from the [Mobility Database](https://database.mobilitydata.org/)
2. Set it as an environment variable:
   ```bash
   export MOBILITY_API_REFRESH_TOKEN=your_token_here
   ```
   
   Or create a `.env` file in your project directory:
   ```bash
   # .env
   MOBILITY_API_REFRESH_TOKEN=your_token_here
   ```

   The client will automatically load the token from either source.

## Basic Usage

```python
from mobility_db_api import MobilityAPI

# Initialize client
# Without token: Uses CSV mode with basic provider information
# With token: Uses API mode with complete, real-time data
api = MobilityAPI()

# Search for providers (works in both modes)
providers = api.get_providers_by_country("BE")
print(f"Found {len(providers)} providers")

# Download a dataset (works in both modes)
if providers:
    dataset_path = api.download_latest_dataset(
        providers[0]['id'],
        download_dir='downloads'
    )
    print(f"Dataset downloaded to: {dataset_path}")

# Force CSV mode even if token is available
api = MobilityAPI(force_csv_mode=True)
```

## What's Next?

- Check the [examples](examples.md) for common use cases
- Read the [API reference](api-reference/client.md) for detailed documentation
- See the [contributing guide](contributing.md) if you want to help improve the client 