import os
import pytest
import requests
from mobility_db_api import MobilityAPI
from pathlib import Path
import shutil
import zipfile
import json
import io

def test_hungary_provider():
    """Test downloading a Hungarian provider's dataset"""
    api = MobilityAPI()
    
    # Get Volánbusz dataset
    dataset_path = api.download_latest_dataset("tld-5862")
    assert dataset_path.exists()
    assert (dataset_path / "feed_info.txt").exists()
    assert (dataset_path / "stops.txt").exists()
    assert (dataset_path / "routes.txt").exists()

def test_belgium_provider():
    """Test downloading a Belgian provider's dataset"""
    api = MobilityAPI()
    
    # Get SNCB dataset
    providers = api.get_providers_by_name("SNCB")
    assert len(providers) > 0
    
    sncb_id = providers[0]["id"]
    dataset_path = api.download_latest_dataset(sncb_id)
    assert dataset_path.exists()
    assert (dataset_path / "feed_info.txt").exists()
    assert (dataset_path / "stops.txt").exists()
    assert (dataset_path / "routes.txt").exists()

def test_country_search():
    """Test searching providers by country"""
    api = MobilityAPI()
    
    # Get Hungarian providers
    providers = api.get_providers_by_country("HU")
    assert len(providers) > 0
    
    # Check if we have some expected providers
    provider_names = [p["provider"] for p in providers]
    assert any("BKK" in name for name in provider_names)  # Budapest
    assert any("Volán" in name for name in provider_names)  # National bus

def test_custom_data_dir():
    """Test using a custom data directory"""
    custom_dir = Path("custom_test_downloads")
    api = MobilityAPI(data_dir=custom_dir)
    
    # Get Volánbusz dataset
    dataset_path = api.download_latest_dataset("tld-5862")
    assert custom_dir in dataset_path.parents
    assert dataset_path.exists()
    
    # Clean up
    shutil.rmtree(custom_dir)

def test_invalid_provider():
    """Test handling of invalid provider ID"""
    api = MobilityAPI()
    
    # Should return None for invalid provider ID
    dataset_path = api.download_latest_dataset("invalid-id-123")
    assert dataset_path is None  # API returns None for invalid provider IDs

def test_invalid_country():
    """Test handling of invalid country code"""
    api = MobilityAPI()
    
    providers = api.get_providers_by_country("XX")  # Invalid country code
    assert len(providers) == 0

def test_no_provider_found():
    """Test handling of provider search with no results"""
    api = MobilityAPI()
    
    providers = api.get_providers_by_name("NonExistentProviderName12345")
    assert len(providers) == 0

def test_direct_download():
    """Test downloading using direct source"""
    api = MobilityAPI()
    
    # Get Volánbusz dataset with direct download
    dataset_path = api.download_latest_dataset("tld-5862", use_direct_source=True)
    assert dataset_path.exists()
    assert (dataset_path / "feed_info.txt").exists()

def test_metadata_tracking():
    """Test metadata tracking functionality"""
    # Use a fresh directory to ensure we get a new download
    data_dir = Path("test_metadata_downloads")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    
    api = MobilityAPI(data_dir=data_dir)
    
    # Download a dataset and check metadata
    dataset_path = api.download_latest_dataset("tld-5862")
    assert dataset_path is not None
    assert dataset_path.exists()
    
    metadata_file = data_dir / "datasets_metadata.json"
    assert metadata_file.exists()
    
    import json
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    assert metadata
    assert isinstance(metadata, dict)
    assert any(entry.get("provider_id") == "tld-5862" for entry in metadata.values())
    
    # Clean up
    shutil.rmtree(data_dir)

def test_token_refresh_error():
    """Test handling of token refresh errors"""
    api = MobilityAPI(refresh_token="invalid_token")
    token = api.get_access_token()
    assert token is None  # Invalid token should return None

def test_network_error(monkeypatch):
    """Test handling of network errors during API calls"""
    def mock_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Network error")
    
    def mock_post(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"access_token": "mock_token"}).encode()
        return response
    
    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)  # Mock token refresh
    api = MobilityAPI()
    
    # Test provider search with network error
    providers = api.get_providers_by_country("HU")
    assert len(providers) == 0
    
    # Test dataset download with network error
    result = api.download_latest_dataset("tld-5862")
    assert result is None

def test_api_error(monkeypatch):
    """Test handling of API errors"""
    def mock_get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 500
        return response
    
    monkeypatch.setattr(requests, "get", mock_get)
    api = MobilityAPI()
    
    # Test provider search with API error
    providers = api.get_providers_by_country("HU")
    assert len(providers) == 0
    
    # Test dataset download with API error
    result = api.download_latest_dataset("tld-5862")
    assert result is None

def test_missing_feed_info():
    """Test handling of missing feed_info.txt"""
    # Create a test directory
    test_dir = Path("test_feed_info")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create a minimal GTFS dataset without feed_info.txt
        dataset_dir = test_dir / "test_dataset"
        dataset_dir.mkdir()
        (dataset_dir / "stops.txt").touch()
        (dataset_dir / "routes.txt").touch()
        
        # Test feed date extraction
        api = MobilityAPI()
        start_date, end_date = api._get_feed_dates(dataset_dir)
        assert start_date is None
        assert end_date is None
    
    finally:
        shutil.rmtree(test_dir)

def test_invalid_feed_info():
    """Test handling of invalid feed_info.txt format"""
    # Create a test directory
    test_dir = Path("test_feed_info")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create a dataset with invalid feed_info.txt
        dataset_dir = test_dir / "test_dataset"
        dataset_dir.mkdir()
        
        # Create feed_info.txt with invalid format
        with open(dataset_dir / "feed_info.txt", "w") as f:
            f.write("invalid,csv,format\n")  # Missing required columns
            f.write("1,2,3\n")
        
        # Test feed date extraction
        api = MobilityAPI()
        start_date, end_date = api._get_feed_dates(dataset_dir)
        assert start_date is None
        assert end_date is None
    
    finally:
        shutil.rmtree(test_dir)

def test_missing_direct_url():
    """Test handling of missing direct download URL"""
    api = MobilityAPI()
    
    # BKK doesn't have a direct URL
    dataset_path = api.download_latest_dataset("o-u-dr_bkk", use_direct_source=True)
    assert dataset_path is None

def test_missing_latest_dataset(monkeypatch):
    """Test handling of missing latest dataset"""
    def mock_get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({
            "provider": "Test Provider",
            "id": "test-id",
            # No latest_dataset field
        }).encode()
        return response
    
    monkeypatch.setattr(requests, "get", mock_get)
    api = MobilityAPI()
    
    result = api.download_latest_dataset("test-id")
    assert result is None

def test_direct_source_hash_comparison(monkeypatch):
    """Test direct source dataset hash comparison"""
    # Create a test ZIP file content
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('test.txt', 'test dataset content')
    zip_content = zip_buffer.getvalue()
    
    # Mock responses
    def mock_get(*args, **kwargs):
        if "gtfs_feeds" in args[0]:  # Provider info request
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({
                "provider": "Test Provider",
                "id": "test-id",
                "source_info": {
                    "producer_url": "http://test.com/dataset.zip"
                }
            }).encode()
            return response
        else:  # Dataset download request
            response = requests.Response()
            response.status_code = 200
            response._content = zip_content  # Return the same ZIP content for both downloads
            return response
    
    def mock_post(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"access_token": "mock_token"}).encode()
        return response
    
    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)
    
    api = MobilityAPI()
    data_dir = Path("test_hash_comparison")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    
    try:
        # First download
        dataset_path = api.download_latest_dataset("test-id", download_dir=str(data_dir), use_direct_source=True)
        assert dataset_path is not None
        assert dataset_path.exists()
        assert (dataset_path / "test.txt").exists()
        
        # Second download should reuse existing dataset if hash matches
        dataset_path_2 = api.download_latest_dataset("test-id", download_dir=str(data_dir), use_direct_source=True)
        assert dataset_path == dataset_path_2  # Same path means reused dataset
        assert (dataset_path_2 / "test.txt").exists()
    
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)

def test_main_script():
    """Test main script functionality"""
    api = MobilityAPI()
    token = api.get_access_token()
    assert token is not None
    assert isinstance(token, str)

def test_dataset_management():
    """Test listing and deleting datasets"""
    # Use a fresh directory
    data_dir = Path("test_dataset_management")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    
    api = MobilityAPI(data_dir=data_dir)
    
    try:
        # Initially no datasets
        assert len(api.list_downloaded_datasets()) == 0
        
        # Download a dataset
        dataset_path = api.download_latest_dataset("tld-5862")
        assert dataset_path is not None
        assert dataset_path.exists()
        
        # Should now have one dataset
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1
        assert datasets[0].provider_id == "tld-5862"
        
        # Try to delete non-existent dataset
        assert not api.delete_dataset("non-existent-id")
        
        # Delete the dataset
        assert api.delete_dataset("tld-5862")
        assert not dataset_path.exists()
        assert len(api.list_downloaded_datasets()) == 0
        
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)