import pytest
import responses
import json
import io
import zipfile
from pathlib import Path
import shutil
from unittest.mock import patch
import requests
from mobility_db_api import MobilityAPI
from mobility_db_api.csv_catalog import CSVCatalog

@pytest.fixture
def test_provider_data():
    """Test provider data fixture."""
    return {
        "id": "mdb-test-1",
        "provider": "Test Provider 1",
        "data_type": "gtfs",
        "status": "",
        "latest_dataset": {
            "id": "test-dataset-1",
            "hosted_url": "http://test1.com/latest",
            "hash": "test_hash_1"
        },
        "source_info": {
            "producer_url": "http://test1.com/direct",
            "license_url": "http://test1.com/license"
        },
        "locations": [
            {
                "country_code": "HU",
                "country": "Hungary",
                "subdivision_name": "Budapest",
                "municipality": "Budapest"
            }
        ]
    }

@pytest.fixture
def mock_dataset_content():
    """Create a mock GTFS dataset."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('feed_info.txt', 'feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\nTest,http://test.com,en,20240101,20241231')
        zip_file.writestr('stops.txt', 'stop_id,stop_name\n1,Test Stop')
    return zip_buffer.getvalue()

def test_get_provider_info_api_mode(test_provider_data, mock_dataset_content):
    """Test getting provider info in API mode with downloaded dataset."""
    test_dir = "test_provider_info"
    api = MobilityAPI(test_dir)
    
    try:
        # Mock API responses
        def mock_get(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            
            if "gtfs_feeds/mdb-test-1" in args[0]:
                response._content = json.dumps(test_provider_data).encode()
            elif "latest" in args[0]:  # Dataset download
                response._content = mock_dataset_content
            return response
        
        def mock_post(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"access_token": "mock_token"}).encode()
            return response
        
        with patch('requests.get', side_effect=mock_get), patch('requests.post', side_effect=mock_post):
            # First get provider info without downloaded dataset
            provider_info = api.get_provider_info("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert "downloaded_dataset" not in provider_info
            
            # Download the dataset
            dataset_path = api.download_latest_dataset("mdb-test-1")
            assert dataset_path is not None
            assert dataset_path.exists()
            
            # Get provider info again, should include downloaded dataset info
            provider_info = api.get_provider_info("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert "downloaded_dataset" in provider_info
            downloaded = provider_info["downloaded_dataset"]
            assert downloaded["dataset_id"] == "test-dataset-1"
            assert downloaded["download_path"] == str(dataset_path)
            assert downloaded["feed_start_date"] == "20240101"
            assert downloaded["feed_end_date"] == "20241231"
            
            # Test with non-existent provider
            provider_info = api.get_provider_info("non-existent")
            assert provider_info is None
            
            # Test with invalid provider ID
            provider_info = api.get_provider_info("invalid-id")
            assert provider_info is None
    
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)

@pytest.fixture
def test_csv_content():
    """Test CSV content fixture."""
    return '''mdb_source_id,data_type,entity_type,location.country_code,location.subdivision_name,location.municipality,provider,name,note,feed_contact_email,static_reference,urls.direct_download,urls.authentication_type,urls.authentication_info,urls.api_key_parameter_name,urls.latest,urls.license,location.bounding_box.minimum_latitude,location.bounding_box.maximum_latitude,location.bounding_box.minimum_longitude,location.bounding_box.maximum_longitude,location.bounding_box.extracted_on,status,features,redirect.id,redirect.comment
test-1,gtfs,,HU,Budapest,Budapest,Test Provider 1,,,,,http://test1.com/direct,,,,http://test1.com/latest,http://test1.com/license,,,,,,,,,
test-2,gtfs,,AT,Vienna,Vienna,Test Provider 2,,,,,http://test2.com/direct,,,,http://test2.com/latest,http://test2.com/license,,,,,,,,,
test-3,gtfs,,HU,Debrecen,Debrecen,Test Provider 3,,,,,http://test3.com/direct,,,,http://test3.com/latest,http://test3.com/license,,,,,,,,,
test-4,gtfs,,US,New York,New York,Inactive Provider,,,,,http://test4.com/direct,,,,http://test4.com/latest,http://test4.com/license,,,,,,inactive,,,
test-5,gtfs,,US,Los Angeles,Los Angeles,Deprecated Provider,,,,,http://test5.com/direct,,,,http://test5.com/latest,http://test5.com/license,,,,,,deprecated,,,
test-6,gtfs,,US,Chicago,Chicago,Redirected Provider,,,,,http://test6.com/direct,,,,http://test6.com/latest,http://test6.com/license,,,,,,,,test-1,
test-7,gbfs,,CA,Toronto,Toronto,GBFS Provider,,,,,http://test7.com/direct,,,,http://test7.com/latest,http://test7.com/license,,,,,,,,,'''

def test_get_provider_info_csv_mode(test_csv_content, mock_dataset_content):
    """Test getting provider info in CSV mode with downloaded dataset."""
    test_dir = "test_provider_info_csv"
    api = MobilityAPI(test_dir, force_csv_mode=True)
    
    try:
        # Mock CSV catalog download
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                CSVCatalog.CATALOG_URL,
                body=test_csv_content,
                status=200
            )
            
            # Mock dataset download
            rsps.add(
                responses.GET,
                "http://test1.com/latest",
                body=mock_dataset_content,
                status=200
            )
            
            # First get provider info without downloaded dataset
            provider_info = api.get_provider_info("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert "downloaded_dataset" not in provider_info
            
            # Download the dataset
            dataset_path = api.download_latest_dataset("mdb-test-1")
            assert dataset_path is not None
            assert dataset_path.exists()
            
            # Get provider info again, should include downloaded dataset info
            provider_info = api.get_provider_info("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert "downloaded_dataset" in provider_info
            downloaded = provider_info["downloaded_dataset"]
            assert downloaded["dataset_id"] is not None
            assert downloaded["download_path"] == str(dataset_path)
            assert downloaded["feed_start_date"] == "20240101"
            assert downloaded["feed_end_date"] == "20241231"
            
            # Test with non-existent provider
            provider_info = api.get_provider_info("non-existent")
            assert provider_info is None
            
            # Test with inactive provider
            provider_info = api.get_provider_info("mdb-test-4")
            assert provider_info is None
            
            # Test with deprecated provider
            provider_info = api.get_provider_info("mdb-test-5")
            assert provider_info is None
            
            # Test with redirected provider
            provider_info = api.get_provider_info("mdb-test-6")
            assert provider_info is None
            
            # Test with non-GTFS provider
            provider_info = api.get_provider_info("mdb-test-7")
            assert provider_info is None
    
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)

def test_get_provider_info_fallback(test_csv_content, mock_dataset_content):
    """Test API to CSV fallback for get_provider_info."""
    test_dir = "test_provider_info_fallback"
    api = MobilityAPI(test_dir)
    
    try:
        # Mock failed API response but successful CSV download
        with responses.RequestsMock() as rsps:
            # Mock token request
            rsps.add(
                responses.POST,
                "https://api.mobilitydatabase.org/v1/tokens",
                json={"access_token": "mock_token"},
                status=200
            )
            
            # Mock failed provider info request
            rsps.add(
                responses.GET,
                "https://api.mobilitydatabase.org/v1/gtfs_feeds/mdb-test-1",
                status=500  # API error
            )
            
            # Mock successful CSV download
            rsps.add(
                responses.GET,
                CSVCatalog.CATALOG_URL,
                body=test_csv_content,
                status=200
            )
            
            # Mock dataset download
            rsps.add(
                responses.GET,
                "http://test1.com/latest",
                body=mock_dataset_content,
                status=200
            )
            
            # Should fall back to CSV catalog
            provider_info = api.get_provider_info("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert api._use_csv is True
            
            # Download dataset and check info again
            dataset_path = api.download_latest_dataset("mdb-test-1")
            assert dataset_path is not None
            assert dataset_path.exists()
            
            provider_info = api.get_provider_info("mdb-test-1")
            assert provider_info is not None
            assert "downloaded_dataset" in provider_info
            downloaded = provider_info["downloaded_dataset"]
            assert downloaded["dataset_id"] is not None
            assert downloaded["download_path"] == str(dataset_path)
            assert downloaded["feed_start_date"] == "20240101"
            assert downloaded["feed_end_date"] == "20241231"
    
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir) 

def test_get_provider_by_id_api_mode(test_provider_data, mock_dataset_content):
    """Test getting provider info by ID in API mode with downloaded dataset."""
    test_dir = "test_provider_info"
    api = MobilityAPI(test_dir)
    
    try:
        # Mock API responses
        def mock_get(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            
            if "gtfs_feeds/mdb-test-1" in args[0]:
                response._content = json.dumps(test_provider_data).encode()
            elif "latest" in args[0]:  # Dataset download
                response._content = mock_dataset_content
            return response
        
        def mock_post(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"access_token": "mock_token"}).encode()
            return response
        
        with patch('requests.get', side_effect=mock_get), patch('requests.post', side_effect=mock_post):
            # First get provider info without downloaded dataset
            provider_info = api.get_provider_by_id("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert "downloaded_dataset" not in provider_info
            
            # Download the dataset
            dataset_path = api.download_latest_dataset("mdb-test-1")
            assert dataset_path is not None
            assert dataset_path.exists()
            
            # Get provider info again, should include downloaded dataset info
            provider_info = api.get_provider_by_id("mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            assert "downloaded_dataset" in provider_info
            downloaded = provider_info["downloaded_dataset"]
            assert downloaded["dataset_id"] == "test-dataset-1"
            assert downloaded["download_path"] == str(dataset_path)
            assert downloaded["feed_start_date"] == "20240101"
            assert downloaded["feed_end_date"] == "20241231"
            
            # Test with non-existent provider
            provider_info = api.get_provider_by_id("non-existent")
            assert provider_info is None
            
            # Test with invalid provider ID
            provider_info = api.get_provider_by_id("invalid-id")
            assert provider_info is None
    
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)

def test_get_provider_info_search_api_mode(test_provider_data, mock_dataset_content):
    """Test searching providers with get_provider_info in API mode."""
    test_dir = "test_provider_info"
    api = MobilityAPI(test_dir)
    
    try:
        # Mock API responses
        def mock_get(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            
            if "gtfs_feeds/mdb-test-1" in args[0]:
                response._content = json.dumps(test_provider_data).encode()
            elif "gtfs_feeds" in args[0]:
                # Handle search queries
                if kwargs.get('params', {}).get('country_code') == "HU":
                    response._content = json.dumps([test_provider_data]).encode()
                elif kwargs.get('params', {}).get('provider') == "Test Provider":
                    response._content = json.dumps([test_provider_data]).encode()
                else:
                    response._content = json.dumps([]).encode()
            elif "latest" in args[0]:  # Dataset download
                response._content = mock_dataset_content
            return response
        
        def mock_post(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"access_token": "mock_token"}).encode()
            return response
        
        with patch('requests.get', side_effect=mock_get), patch('requests.post', side_effect=mock_post):
            # Test search by ID
            provider_info = api.get_provider_info(provider_id="mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            
            # Test search by country
            providers = api.get_provider_info(country_code="HU")
            assert len(providers) == 1
            assert providers[0]["id"] == "mdb-test-1"
            assert providers[0]["provider"] == "Test Provider 1"
            
            # Test search by name
            providers = api.get_provider_info(name="Test Provider")
            assert len(providers) == 1
            assert providers[0]["id"] == "mdb-test-1"
            assert providers[0]["provider"] == "Test Provider 1"
            
            # Test with no criteria
            providers = api.get_provider_info()
            assert len(providers) == 0
            
            # Test with non-existent values
            assert api.get_provider_info(provider_id="non-existent") is None
            assert len(api.get_provider_info(country_code="XX")) == 0
            assert len(api.get_provider_info(name="NonExistent")) == 0
    
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)

def test_get_provider_info_search_csv_mode(test_csv_content, mock_dataset_content):
    """Test searching providers with get_provider_info in CSV mode."""
    test_dir = "test_provider_info_csv"
    api = MobilityAPI(test_dir, force_csv_mode=True)
    
    try:
        # Mock CSV catalog download
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                CSVCatalog.CATALOG_URL,
                body=test_csv_content,
                status=200
            )
            
            # Test search by ID
            provider_info = api.get_provider_info(provider_id="mdb-test-1")
            assert provider_info is not None
            assert provider_info["id"] == "mdb-test-1"
            assert provider_info["provider"] == "Test Provider 1"
            
            # Test search by country
            providers = api.get_provider_info(country_code="HU")
            assert len(providers) == 2
            assert providers[0]["id"] == "mdb-test-1"
            assert providers[1]["id"] == "mdb-test-3"
            
            # Test search by name
            providers = api.get_provider_info(name="Test Provider")
            assert len(providers) == 3  # Should find Test Provider 1, 2, and 3
            
            # Test with no criteria
            providers = api.get_provider_info()
            assert len(providers) == 0
            
            # Test with non-existent values
            assert api.get_provider_info(provider_id="non-existent") is None
            assert len(api.get_provider_info(country_code="XX")) == 0
            assert len(api.get_provider_info(name="NonExistent")) == 0
            
            # Test with inactive/deprecated providers
            assert api.get_provider_info(provider_id="mdb-test-4") is None  # Inactive
            assert api.get_provider_info(provider_id="mdb-test-5") is None  # Deprecated
            assert api.get_provider_info(provider_id="mdb-test-6") is None  # Redirected
            assert api.get_provider_info(provider_id="mdb-test-7") is None  # Non-GTFS
    
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir) 

def test_get_provider_by_id_no_args():
    """Test calling get_provider_by_id without arguments."""
    api = MobilityAPI()
    with pytest.raises(TypeError):
        api.get_provider_by_id()

def test_get_providers_by_country_no_args():
    """Test calling get_providers_by_country without arguments."""
    api = MobilityAPI()
    with pytest.raises(TypeError):
        api.get_providers_by_country()

def test_get_providers_by_name_no_args():
    """Test calling get_providers_by_name without arguments."""
    api = MobilityAPI()
    with pytest.raises(TypeError):
        api.get_providers_by_name()

def test_get_provider_info_no_args_explicit():
    """Test explicitly calling get_provider_info without any arguments."""
    api = MobilityAPI()
    providers = api.get_provider_info()
    assert isinstance(providers, list)
    assert len(providers) == 0

def test_get_provider_info_empty_args():
    """Test calling get_provider_info with empty strings."""
    api = MobilityAPI()
    
    # Empty provider_id should return None
    assert api.get_provider_info(provider_id="") is None
    
    # Empty country_code should return empty list
    providers = api.get_provider_info(country_code="")
    assert isinstance(providers, list)
    assert len(providers) == 0
    
    # Empty name should return all providers (since empty string matches all names)
    providers = api.get_provider_info(name="")
    assert isinstance(providers, list)
    assert len(providers) > 0  # Should return all active GTFS providers 