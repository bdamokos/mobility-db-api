# Mobility Database API Explorer

This project provides tools to interact with the Mobility Database API and explore GTFS data from various transit providers.

## Setup

1. Create and activate a Python virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your API tokens:
   - Copy your access token and refresh token to the `.env` file
   - Replace `your_access_token_here` and `your_refresh_token_here` with your actual tokens

## Usage

### Interactive Exploration
Launch Jupyter Notebook:
```bash
jupyter notebook
```
Then open `explore_mobility_data.ipynb` for interactive data exploration.

### Script Usage
Run the Python script directly:
```bash
python mobility_api.py
```

## Authentication Types
The API uses different authentication types:
- Type 0: No authentication required
- Type 1: Username/password required
- Type 2: API key required
- Type 3: OAuth required
- Type 4: Other authentication method

Currently, the script automatically downloads GTFS data for providers with authentication_type 0. 