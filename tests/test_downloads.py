import os
import pytest
import requests
from mobility_db_api import MobilityAPI
from pathlib import Path
import shutil
import zipfile
import json
import io
from typing import Dict, Set
from unittest.mock import patch

def test_smallest_dataset():
    """Test downloading the smallest known dataset"""
    api = MobilityAPI()
    
    # Get the smallest dataset we found (mdb-859, ~3.1 KB)
    dataset_path = api.download_latest_dataset("mdb-859")
    assert dataset_path.exists()
    assert (dataset_path / "stops.txt").exists()
    assert (dataset_path / "routes.txt").exists()

def test_multiple_small_datasets():
    """Test downloading multiple small datasets"""
    api = MobilityAPI()
    
    # Test with a few small datasets we found
    small_datasets = [
        "mdb-2036",  # ~10.3 KB
        "mdb-685",   # ~12.3 KB
        "mdb-1860",  # ~12.9 KB
    ]
    
    for provider_id in small_datasets:
        dataset_path = api.download_latest_dataset(provider_id)
        assert dataset_path.exists()
        assert (dataset_path / "stops.txt").exists()
        assert (dataset_path / "routes.txt").exists()

def test_country_search():
    """Test searching providers by country"""
    api = MobilityAPI()
    
    # Get providers from a country with small datasets
    providers = api.get_providers_by_country("LU")  # Luxembourg
    assert len(providers) > 0

def test_custom_data_dir(monkeypatch):
    """Test using a custom data directory"""
    # Create a mock session class
    class MockSession:
        def __init__(self):
            self.headers = {}

        def get(self, *args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            if "gtfs_feeds" in args[0]:  # Provider info request
                response._content = json.dumps({
                    "provider": "Test Provider",
                    "latest_dataset": {
                        "id": "test-dataset",
                        "hosted_url": "http://test.com/dataset.zip"
                    }
                }).encode()
            else:  # Dataset download request
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    zip_file.writestr('test.txt', 'test dataset content')
                response._content = zip_buffer.getvalue()
            return response

        def post(self, *args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"access_token": "mock_token"}).encode()
            return response

        def close(self):
            pass

    monkeypatch.setattr(requests, "Session", lambda: MockSession())
    custom_dir = Path("custom_test_downloads")
    api = MobilityAPI(data_dir=custom_dir)

    # Use our smallest dataset for testing
    dataset_path = api.download_latest_dataset("mdb-859")
    assert custom_dir in dataset_path.parents

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

def test_metadata_tracking(monkeypatch):
    """Test metadata tracking functionality"""
    def mock_get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        if "gtfs_feeds" in args[0]:  # Provider info request
            response._content = json.dumps({
                "provider": "Test Provider",
                "latest_dataset": {
                    "id": "test-dataset",
                    "hosted_url": "http://test.com/dataset.zip"
                }
            }).encode()
        else:  # Dataset download request
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                zip_file.writestr('test.txt', 'test dataset content')
            response._content = zip_buffer.getvalue()
        return response

    def mock_post(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"access_token": "mock_token"}).encode()
        return response

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)

    # Use a fresh directory to ensure we get a new download
    data_dir = Path("test_metadata_downloads")
    if data_dir.exists():
        shutil.rmtree(data_dir)

    api = MobilityAPI(data_dir=data_dir)

    try:
        # Download a dataset and check metadata
        dataset_path = api.download_latest_dataset("tld-5862")
        assert dataset_path is not None
        assert dataset_path.exists()

        # Check metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1
        metadata = datasets[0]
        assert metadata.provider_id == "tld-5862"
        assert metadata.provider_name == "Test Provider"
        assert metadata.dataset_id == "test-dataset"
        assert metadata.download_path == dataset_path

    finally:
        if data_dir.exists():
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
    # Should fall back to CSV catalog and return providers
    providers = api.get_providers_by_country("HU")
    assert len(providers) > 0  # Should get providers from CSV
    assert api._use_csv is True  # Should switch to CSV mode
    
    # Test dataset download with network error
    result = api.download_latest_dataset("tld-5862")
    assert result is None  # Download should still fail

def test_api_error(monkeypatch):
    """Test handling of API errors"""
    def mock_get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 500
        return response

    def mock_post(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"access_token": "mock_token"}).encode()
        return response

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)
    api = MobilityAPI()

    # Test provider search with API error
    providers = api.get_providers_by_country("HU")
    assert len(providers) == 0

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

    def mock_get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        if "gtfs_feeds" in args[0]:  # Provider info request
            response._content = json.dumps({
                "provider": "Test Provider",
                "id": "test-id",
                "source_info": {
                    "producer_url": "http://test.com/dataset.zip"
                }
            }).encode()
        else:  # Dataset download request
            response._content = zip_content
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

        # Second download should reuse existing dataset
        new_dataset_path = api.download_latest_dataset("test-id", download_dir=str(data_dir), use_direct_source=True)
        assert new_dataset_path == dataset_path

    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)

def test_main_script():
    """Test main script functionality"""
    api = MobilityAPI()
    token = api.get_access_token()
    assert token is not None
    assert isinstance(token, str)

def test_dataset_management(monkeypatch):
    """Test listing and deleting datasets"""
    # Create a mock session class
    class MockSession:
        def __init__(self):
            self.headers = {}

        def get(self, *args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            if "gtfs_feeds" in args[0]:  # Provider info request
                response._content = json.dumps({
                    "provider": "Test Provider",
                    "latest_dataset": {
                        "id": "test-dataset",
                        "hosted_url": "http://test.com/dataset.zip"
                    }
                }).encode()
            else:  # Dataset download request
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    zip_file.writestr('test.txt', 'test dataset content')
                response._content = zip_buffer.getvalue()
            return response

        def post(self, *args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"access_token": "mock_token"}).encode()
            return response

        def close(self):
            pass

    monkeypatch.setattr(requests, "Session", lambda: MockSession())

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

        # Check dataset is listed
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1

        # Delete dataset
        assert api.delete_dataset("tld-5862")
        assert len(api.list_downloaded_datasets()) == 0

    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)

def test_dataset_update_with_new_hash(monkeypatch):
    """Test handling of dataset updates when API reports a new version with different hash"""
    # Create two different test datasets
    old_content = b'old dataset content'
    new_content = b'new dataset content - updated version'
    
    # Track which content should be returned
    return_new_version = False
    
    def mock_get(*args, **kwargs):
        nonlocal return_new_version
        response = requests.Response()
        response.status_code = 200
        
        if "gtfs_feeds" in args[0]:  # Provider info request
            dataset_id = "test-dataset-v1" if not return_new_version else "test-dataset-v2"
            dataset_hash = "old_hash" if not return_new_version else "new_hash"
            response._content = json.dumps({
                "provider": "Test Provider",
                "latest_dataset": {
                    "id": dataset_id,
                    "hosted_url": "http://test.com/dataset.zip",
                    "hash": dataset_hash
                }
            }).encode()
        else:  # Dataset download request
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                zip_file.writestr('test.txt', old_content if not return_new_version else new_content)
            response._content = zip_buffer.getvalue()
        return response

    def mock_post(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"access_token": "mock_token"}).encode()
        return response

    monkeypatch.setattr(requests, "get", mock_get)
    monkeypatch.setattr(requests, "post", mock_post)

    # Use a fresh directory
    data_dir = Path("test_dataset_updates")
    if data_dir.exists():
        shutil.rmtree(data_dir)

    api = MobilityAPI(data_dir=data_dir)

    try:
        # First download with old version
        first_path = api.download_latest_dataset("test-provider")
        assert first_path is not None
        assert first_path.exists()
        
        # Verify old content
        with open(first_path / "test.txt", "rb") as f:
            assert f.read() == old_content
        
        # Switch to new version
        return_new_version = True
        
        # Download again - should get new version
        second_path = api.download_latest_dataset("test-provider")
        assert second_path is not None
        assert second_path.exists()
        assert second_path != first_path  # Should be a different path
        
        # Verify new content
        with open(second_path / "test.txt", "rb") as f:
            assert f.read() == new_content
        
        # Old path should be cleaned up
        assert not first_path.exists()
        
        # Metadata should be updated
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1  # Should only have the new version
        assert datasets[0].dataset_id == "test-dataset-v2"

    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)

def test_real_dataset_update():
    """Test downloading a dataset and then updating it when a new version is available."""
    test_dir = "test_real_updates"
    test_data_dir = "test_data_storage"  # Separate directory for our test data
    api = MobilityAPI(test_dir)

    # Use our two smallest known datasets
    dataset_a_id = "mdb-859"  # 3.1 KB
    dataset_b_id = "mdb-2036"  # 10.3 KB
    
    try:
        print("\nStep 1: Initial downloads to temporary storage")
        # First download both datasets to our test data storage
        temp_api = MobilityAPI(test_data_dir)
        dataset_a_path = temp_api.download_latest_dataset(dataset_a_id)
        assert dataset_a_path is not None, "Dataset A download failed"
        assert dataset_a_path.exists(), "Dataset A path does not exist"
        print("✓ Dataset A downloaded successfully")
        
        dataset_b_path = temp_api.download_latest_dataset(dataset_b_id)
        assert dataset_b_path is not None, "Dataset B download failed"
        assert dataset_b_path.exists(), "Dataset B path does not exist"
        print("✓ Dataset B downloaded successfully")
        
        print(f"\nStep 2: Reading dataset contents")
        # Store both datasets' content
        dataset_a_content = {}
        dataset_b_content = {}
        
        for file_path in dataset_a_path.rglob('*'):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    dataset_a_content[file_path.name] = f.read()
        print(f"✓ Read {len(dataset_a_content)} files from dataset A")
        
        for file_path in dataset_b_path.rglob('*'):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    dataset_b_content[file_path.name] = f.read()
        print(f"✓ Read {len(dataset_b_content)} files from dataset B")
        
        print("\nStep 3: Getting dataset A's metadata")
        # Get dataset A's real metadata
        url = f"{api.base_url}/gtfs_feeds/{dataset_a_id}"
        dataset_a_info = requests.get(url, headers=api._get_headers()).json()
        print("✓ Got dataset A's metadata")
        
        print("\nStep 4: Clean up test directory and metadata")
        # Clean up test directory to start fresh
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)
        Path(test_dir).mkdir()
        # Clean up metadata file if it exists
        metadata_file = Path(test_dir) / "dataset_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()
        print("✓ Test directory and metadata cleaned up")
        
        print("\nStep 5: Setting up mock responses")
        # Create mock that first serves A's metadata, then B's content with updated A metadata
        is_second_request = False
        first_dataset_id = None  # Store the first dataset ID
        def mock_get(*args, **kwargs):
            nonlocal is_second_request, first_dataset_id
            response = requests.Response()
            response.status_code = 200
            
            if f"gtfs_feeds/{dataset_a_id}" in args[0]:
                # First time: return A's real metadata
                # Second time: return A's metadata with updated hash and dataset ID
                if not is_second_request:
                    response._content = json.dumps(dataset_a_info).encode()
                    first_dataset_id = dataset_a_info['latest_dataset']['id']  # Store the first dataset ID
                else:
                    modified_info = dataset_a_info.copy()
                    modified_info['latest_dataset'] = {
                        'id': 'mdb-2036-202408190034',  # Use a new dataset ID for the second download
                        'hash': 'updated_hash_value',
                        'hosted_url': f"https://files.mobilitydatabase.org/mdb-2036/mdb-2036-202408190034/mdb-2036-202408190034.zip"  # Use dataset B's real URL
                    }
                    response._content = json.dumps(modified_info).encode()
            elif ".zip" in args[0]:
                # First time: return A's content
                # Second time: return B's content
                if not is_second_request:
                    is_second_request = True
                    # Create a zip file with dataset A's content
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w') as zf:
                        for filename, content in dataset_a_content.items():
                            zf.writestr(filename, content)
                    response._content = zip_buffer.getvalue()
                else:
                    # Create a zip file with dataset B's content
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w') as zf:
                        for filename, content in dataset_b_content.items():
                            zf.writestr(filename, content)
                    response._content = zip_buffer.getvalue()
            return response
        print("✓ Mock responses ready")
        
        print("\nStep 6: Testing with mock responses")
        with patch('requests.get', side_effect=mock_get):
            # First download - should get A's content
            print("\nFirst mock download (should get A's content):")
            first_path = api.download_latest_dataset(dataset_a_id)
            assert first_path is not None, "First mock download failed"
            assert first_path.exists(), "First mock download path does not exist"
            print("✓ First download successful")
            
            # Second download - should get B's content
            print("\nSecond mock download (should get B's content):")
            second_path = api.download_latest_dataset(dataset_a_id)
            assert second_path is not None, "Second mock download failed"
            assert second_path.exists(), "Second mock download path does not exist"
            assert second_path != first_path, "Second download path should be different"
            print("✓ Second download successful")
            
            # Verify the paths
            assert not first_path.exists(), "Old path should be gone"
            print("✓ Old path was cleaned up")
            
            # Metadata should be updated
            datasets = api.list_downloaded_datasets()
            assert len(datasets) == 1, "Should have exactly one dataset"
            metadata = datasets[0]
            assert metadata.provider_id == dataset_a_id, "Provider ID mismatch"
            assert metadata.api_provided_hash == 'updated_hash_value', "Hash not updated"
            assert metadata.dataset_id == 'mdb-2036-202408190034', "Dataset ID not updated"
            assert metadata.download_path == second_path, "Download path mismatch"
            print("✓ Metadata updated correctly")
            
            # Compare file contents
            def get_dir_contents(path):
                return {f.name for f in Path(path).rglob('*') if f.is_file()}
            
            # Files should match dataset B's files
            second_path_files = get_dir_contents(second_path)
            expected_files = set(dataset_b_content.keys())
            assert second_path_files == expected_files, f"File mismatch. Found: {second_path_files}, Expected: {expected_files}"
            print("✓ File contents match expected dataset")
    
    finally:
        # Clean up both directories
        for dir_path in [test_dir, test_data_dir]:
            if Path(dir_path).exists():
                print(f"\nCleaning up directory: {dir_path}")
                shutil.rmtree(dir_path)
                print(f"✓ {dir_path} cleaned up")

def test_selective_dataset_deletion():
    """Test that deleting a specific dataset leaves other datasets intact."""
    test_dir = "test_selective_deletion"
    api = MobilityAPI(test_dir)
    
    # Use our three smallest known datasets
    dataset_a_id = "mdb-859"   # 3.1 KB
    dataset_b_id = "mdb-2036"  # 10.3 KB
    dataset_c_id = "mdb-685"   # 12.3 KB
    
    try:
        print("\nStep 1: Download all three datasets")
        # Download all datasets
        path_a = api.download_latest_dataset(dataset_a_id)
        assert path_a is not None, "Dataset A download failed"
        assert path_a.exists(), "Dataset A path does not exist"
        print("✓ Dataset A downloaded successfully")
        
        path_b = api.download_latest_dataset(dataset_b_id)
        assert path_b is not None, "Dataset B download failed"
        assert path_b.exists(), "Dataset B path does not exist"
        print("✓ Dataset B downloaded successfully")
        
        path_c = api.download_latest_dataset(dataset_c_id)
        assert path_c is not None, "Dataset C download failed"
        assert path_c.exists(), "Dataset C path does not exist"
        print("✓ Dataset C downloaded successfully")
        
        print("\nStep 2: Verify initial state")
        # Verify all datasets exist
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 3, "Should have all three datasets"
        dataset_ids = {d.provider_id for d in datasets}
        assert dataset_ids == {dataset_a_id, dataset_b_id, dataset_c_id}, "Missing some datasets"
        print("✓ Initial state verified")
        
        print("\nStep 3: Delete dataset B")
        # Delete dataset B
        success = api.delete_dataset(dataset_b_id)
        assert success, "Dataset B deletion failed"
        print("✓ Dataset B deleted")
        
        print("\nStep 4: Verify final state")
        # Verify dataset B is gone but A and C remain
        assert not path_b.exists(), "Dataset B path should not exist"
        assert path_a.exists(), "Dataset A should still exist"
        assert path_c.exists(), "Dataset C should still exist"
        print("✓ Filesystem state verified")
        
        # Verify metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 2, "Should have two datasets"
        dataset_ids = {d.provider_id for d in datasets}
        assert dataset_ids == {dataset_a_id, dataset_c_id}, "Metadata doesn't match expected state"
        print("✓ Metadata state verified")
    
    finally:
        # Clean up
        if Path(test_dir).exists():
            print("\nCleaning up test directory")
            shutil.rmtree(test_dir)
            print("✓ Test directory cleaned up")

def test_delete_provider_datasets():
    """Test deleting all datasets for a specific provider."""
    test_dir = "test_provider_deletion"
    api = MobilityAPI(test_dir)
    
    # Use our three smallest known datasets
    # Two from one provider, one from another
    dataset_a_id = "mdb-859"   # 3.1 KB
    dataset_b_id = "mdb-2036"  # 10.3 KB
    dataset_c_id = "mdb-685"   # 12.3 KB
    
    try:
        print("\nStep 1: Download all datasets")
        # Download all datasets
        path_a = api.download_latest_dataset(dataset_a_id)
        assert path_a is not None, "Dataset A download failed"
        assert path_a.exists(), "Dataset A path does not exist"
        print("✓ Dataset A downloaded successfully")
        
        path_b = api.download_latest_dataset(dataset_b_id)
        assert path_b is not None, "Dataset B download failed"
        assert path_b.exists(), "Dataset B path does not exist"
        print("✓ Dataset B downloaded successfully")
        
        path_c = api.download_latest_dataset(dataset_c_id)
        assert path_c is not None, "Dataset C download failed"
        assert path_c.exists(), "Dataset C path does not exist"
        print("✓ Dataset C downloaded successfully")
        
        print("\nStep 2: Verify initial state")
        # Verify all datasets exist
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 3, "Should have all three datasets"
        dataset_ids = {d.provider_id for d in datasets}
        assert dataset_ids == {dataset_a_id, dataset_b_id, dataset_c_id}, "Missing some datasets"
        print("✓ Initial state verified")
        
        print("\nStep 3: Delete all datasets for provider A")
        # Delete all datasets for provider A
        success = api.delete_provider_datasets(dataset_a_id)
        assert success, "Provider A dataset deletion failed"
        print("✓ Provider A datasets deleted")
        
        print("\nStep 4: Verify final state")
        # Verify provider A datasets are gone but others remain
        assert not path_a.exists(), "Dataset A path should not exist"
        assert path_b.exists(), "Dataset B should still exist"
        assert path_c.exists(), "Dataset C should still exist"
        print("✓ Filesystem state verified")
        
        # Verify metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 2, "Should have two datasets"
        dataset_ids = {d.provider_id for d in datasets}
        assert dataset_ids == {dataset_b_id, dataset_c_id}, "Metadata doesn't match expected state"
        print("✓ Metadata state verified")
    
    finally:
        # Clean up
        if Path(test_dir).exists():
            print("\nCleaning up test directory")
            shutil.rmtree(test_dir)
            print("✓ Test directory cleaned up")

def test_delete_all_datasets():
    """Test deleting all downloaded datasets."""
    test_dir = "test_all_deletion"
    api = MobilityAPI(test_dir)
    
    # Use our three smallest known datasets
    dataset_a_id = "mdb-859"   # 3.1 KB
    dataset_b_id = "mdb-2036"  # 10.3 KB
    dataset_c_id = "mdb-685"   # 12.3 KB
    
    try:
        print("\nStep 1: Download all datasets")
        # Download all datasets
        path_a = api.download_latest_dataset(dataset_a_id)
        assert path_a is not None, "Dataset A download failed"
        assert path_a.exists(), "Dataset A path does not exist"
        print("✓ Dataset A downloaded successfully")
        
        path_b = api.download_latest_dataset(dataset_b_id)
        assert path_b is not None, "Dataset B download failed"
        assert path_b.exists(), "Dataset B path does not exist"
        print("✓ Dataset B downloaded successfully")
        
        path_c = api.download_latest_dataset(dataset_c_id)
        assert path_c is not None, "Dataset C download failed"
        assert path_c.exists(), "Dataset C path does not exist"
        print("✓ Dataset C downloaded successfully")
        
        print("\nStep 2: Verify initial state")
        # Verify all datasets exist
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 3, "Should have all three datasets"
        dataset_ids = {d.provider_id for d in datasets}
        assert dataset_ids == {dataset_a_id, dataset_b_id, dataset_c_id}, "Missing some datasets"
        print("✓ Initial state verified")
        
        print("\nStep 3: Delete all datasets")
        # Delete all datasets
        success = api.delete_all_datasets()
        assert success, "All datasets deletion failed"
        print("✓ All datasets deleted")
        
        print("\nStep 4: Verify final state")
        # Verify all datasets are gone
        assert not path_a.exists(), "Dataset A path should not exist"
        assert not path_b.exists(), "Dataset B path should not exist"
        assert not path_c.exists(), "Dataset C path should not exist"
        print("✓ Filesystem state verified")
        
        # Verify metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 0, "Should have no datasets"
        print("✓ Metadata state verified")
        
        # Test deleting when no datasets exist
        success = api.delete_all_datasets()
        assert success, "Deleting no datasets should succeed"
        print("✓ Empty deletion succeeded")
    
    finally:
        # Clean up
        if Path(test_dir).exists():
            print("\nCleaning up test directory")
            shutil.rmtree(test_dir)
            print("✓ Test directory cleaned up")

def test_directory_cleanup_behavior():
    """Test the cleanup behavior of deletion methods with various directory structures."""
    test_dir = "test_cleanup_behavior"
    api = MobilityAPI(test_dir)
    
    # Use our smallest datasets
    dataset_a_id = "mdb-859"   # 3.1 KB
    dataset_b_id = "mdb-2036"  # 10.3 KB
    
    try:
        print("\nStep 1: Setting up test directory structure")
        base_dir = Path(test_dir)
        
        # Create some unrelated files and directories that should be preserved
        unrelated_dir = base_dir / "unrelated_dir"
        unrelated_dir.mkdir(parents=True)
        (unrelated_dir / "keep_this_file.txt").write_text("important content")
        
        # Create a custom file in the main data directory
        (base_dir / "custom_file.txt").write_text("custom content")
        
        print("✓ Created unrelated files and directories")
        
        print("\nStep 2: Download datasets")
        # Download first dataset
        path_a = api.download_latest_dataset(dataset_a_id)
        assert path_a is not None, "Dataset A download failed"
        assert path_a.exists(), "Dataset A path does not exist"
        
        # Create a custom file in the provider directory
        provider_dir_a = path_a.parent
        (provider_dir_a / "provider_specific.txt").write_text("provider content")
        
        # Download second dataset from same provider (if possible)
        path_a2 = api.download_latest_dataset(dataset_a_id)
        if path_a2 and path_a2 != path_a:  # If we got a different version
            assert path_a2.exists(), "Dataset A2 path does not exist"
        
        # Download dataset from different provider
        path_b = api.download_latest_dataset(dataset_b_id)
        assert path_b is not None, "Dataset B download failed"
        assert path_b.exists(), "Dataset B path does not exist"
        print("✓ Downloaded datasets and created provider-specific files")
        
        print("\nStep 3: Verify initial structure")
        assert base_dir.exists(), "Base directory should exist"
        assert unrelated_dir.exists(), "Unrelated directory should exist"
        assert (base_dir / "custom_file.txt").exists(), "Custom file should exist"
        assert (provider_dir_a / "provider_specific.txt").exists(), "Provider-specific file should exist"
        print("✓ Initial directory structure verified")
        
        print("\nStep 4: Test single dataset deletion")
        # Delete one dataset but keep provider-specific file
        success = api.delete_dataset(dataset_a_id)
        assert success, "Dataset deletion failed"
        assert (provider_dir_a / "provider_specific.txt").exists(), "Provider-specific file should be preserved"
        assert unrelated_dir.exists(), "Unrelated directory should be preserved"
        assert (base_dir / "custom_file.txt").exists(), "Custom file should be preserved"
        print("✓ Single dataset deletion preserved other files")
        
        print("\nStep 5: Test provider deletion")
        # Create a new dataset for the first provider
        path_a_new = api.download_latest_dataset(dataset_a_id)
        assert path_a_new is not None, "New dataset A download failed"
        
        # Delete all datasets for provider A
        success = api.delete_provider_datasets(dataset_a_id)
        assert success, "Provider datasets deletion failed"
        
        # Provider directory should still exist if it has custom files
        if (provider_dir_a / "provider_specific.txt").exists():
            assert provider_dir_a.exists(), "Provider directory should exist when it has custom files"
        print("✓ Provider deletion preserved custom files")
        
        print("\nStep 6: Test complete cleanup")
        # Remove provider-specific file
        if (provider_dir_a / "provider_specific.txt").exists():
            (provider_dir_a / "provider_specific.txt").unlink()
        
        # Download new datasets
        path_a_final = api.download_latest_dataset(dataset_a_id)
        assert path_a_final is not None, "Final dataset A download failed"
        
        # Delete all datasets
        success = api.delete_all_datasets()
        assert success, "All datasets deletion failed"
        
        print("\nStep 7: Verify final state")
        # These should still exist
        assert base_dir.exists(), "Base directory should still exist"
        assert unrelated_dir.exists(), "Unrelated directory should still exist"
        assert (base_dir / "custom_file.txt").exists(), "Custom file should still exist"
        assert (unrelated_dir / "keep_this_file.txt").exists(), "Unrelated file should still exist"
        
        # Provider directory should be gone if it had no custom files
        if not (provider_dir_a / "provider_specific.txt").exists():
            assert not provider_dir_a.exists(), "Empty provider directory should be removed"
        
        # Verify metadata state
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 0, "Should have no datasets in metadata"
        print("✓ Final state verified - all datasets removed, custom files preserved")
        
    finally:
        # Clean up
        if base_dir.exists():
            print("\nCleaning up test directory")
            shutil.rmtree(base_dir)
            print("✓ Test directory cleaned up")

def test_force_csv_mode():
    """Test that force_csv_mode always uses CSV catalog"""
    api = MobilityAPI(force_csv_mode=True)
    
    # Should use CSV catalog even with valid token
    api.refresh_token = "valid_token"  # This would normally trigger API mode
    assert api._use_csv is True
    
    # CSV catalog should not be initialized until needed
    assert api._csv_catalog is None
    
    # Should initialize CSV catalog on first use
    providers = api.get_providers_by_country("HU")
    assert api._csv_catalog is not None

def test_lazy_csv_initialization():
    """Test that CSV catalog is only initialized when needed"""
    api = MobilityAPI()
    
    # CSV catalog should not be initialized yet
    assert api._csv_catalog is None
    
    # Force CSV mode
    api = MobilityAPI(force_csv_mode=True)
    
    # CSV catalog should still not be initialized
    assert api._csv_catalog is None
    
    # Should initialize when first used
    providers = api.get_providers_by_country("HU")
    assert api._csv_catalog is not None
    assert len(providers) > 0  # Should get actual providers

def test_csv_initial_network_error(monkeypatch):
    """Test handling of network errors during initial CSV download"""
    def mock_get(*args, **kwargs):
        # Simulate network error for all requests
        raise requests.exceptions.ConnectionError("Network error")
    
    monkeypatch.setattr(requests, "get", mock_get)
    
    # Use a fresh directory to ensure no cached CSV
    test_dir = "test_csv_network_error"
    if Path(test_dir).exists():
        shutil.rmtree(test_dir)
    
    try:
        api = MobilityAPI(data_dir=test_dir, force_csv_mode=True)
        
        # Attempt to get providers should fail as we can't download CSV
        providers = api.get_providers_by_country("HU")
        assert len(providers) == 0, "Should return empty list when CSV download fails"
        
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)

def test_csv_fallback_with_cached(monkeypatch):
    """Test CSV fallback when network is down but CSV is already cached"""
    # First, let's get a clean setup with CSV downloaded
    test_dir = "test_csv_cached"
    if Path(test_dir).exists():
        shutil.rmtree(test_dir)
    
    try:
        # First, download CSV normally
        api = MobilityAPI(data_dir=test_dir, force_csv_mode=True)
        initial_providers = api.get_providers_by_country("HU")
        assert len(initial_providers) > 0, "Should get providers in initial download"
        
        # Now simulate network error
        def mock_get(*args, **kwargs):
            raise requests.exceptions.ConnectionError("Network error")
        
        monkeypatch.setattr(requests, "get", mock_get)
        
        # Create new API instance pointing to same directory
        api_offline = MobilityAPI(data_dir=test_dir, force_csv_mode=True)
        
        # Should still work using cached CSV
        offline_providers = api_offline.get_providers_by_country("HU")
        assert len(offline_providers) > 0, "Should get providers from cached CSV"
        assert offline_providers == initial_providers, "Should get same providers as before"
        
    finally:
        if Path(test_dir).exists():
            shutil.rmtree(test_dir)