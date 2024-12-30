import pytest
from pathlib import Path
import zipfile
import io
import shutil
from datetime import datetime
from mobility_db_api import ExternalGTFSAPI

@pytest.fixture
def test_gtfs_content():
    """Create a mock GTFS dataset with single agency."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('agency.txt', 
            'agency_id,agency_name,agency_url,agency_timezone\n'
            '1,Test Agency,http://test.com,Europe/London'
        )
        zip_file.writestr('feed_info.txt',
            'feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\n'
            'Test,http://test.com,en,20240101,20241231'
        )
    return zip_buffer.getvalue()

@pytest.fixture
def test_gtfs_multi_agency():
    """Create a mock GTFS dataset with multiple agencies."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('agency.txt', 
            'agency_id,agency_name,agency_url,agency_timezone\n'
            '1,Agency One,http://one.com,Europe/London\n'
            '2,Agency Two,http://two.com,Europe/London'
        )
        zip_file.writestr('feed_info.txt',
            'feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\n'
            'Test,http://test.com,en,20240101,20241231'
        )
    return zip_buffer.getvalue()

def test_extract_gtfs_basic(test_gtfs_content):
    """Test basic GTFS extraction with automatic provider ID and name."""
    test_dir = Path("test_external_basic")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create a temporary GTFS file
        zip_path = test_dir / "test.zip"
        test_dir.mkdir(exist_ok=True)
        with open(zip_path, "wb") as f:
            f.write(test_gtfs_content)
        
        # Extract the GTFS file
        dataset_path = api.extract_gtfs(zip_path)
        assert dataset_path is not None
        assert dataset_path.exists()
        assert (dataset_path / "agency.txt").exists()
        assert (dataset_path / "feed_info.txt").exists()
        
        # Check metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1
        dataset = datasets[0]
        assert dataset.provider_id.startswith("ext-")
        assert dataset.provider_name == "Test Agency"
        assert dataset.is_direct_source is True
        assert dataset.feed_start_date == "20240101"
        assert dataset.feed_end_date == "20241231"
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_multi_agency(test_gtfs_multi_agency):
    """Test GTFS extraction with multiple agencies."""
    test_dir = Path("test_external_multi")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create a temporary GTFS file
        zip_path = test_dir / "test.zip"
        test_dir.mkdir(exist_ok=True)
        with open(zip_path, "wb") as f:
            f.write(test_gtfs_multi_agency)
        
        # Extract the GTFS file
        dataset_path = api.extract_gtfs(zip_path)
        assert dataset_path is not None
        
        # Check metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1
        dataset = datasets[0]
        assert dataset.provider_name == "Agency One, Agency Two"
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_custom_name(test_gtfs_content):
    """Test GTFS extraction with custom provider name."""
    test_dir = Path("test_external_custom")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create a temporary GTFS file
        zip_path = test_dir / "test.zip"
        test_dir.mkdir(exist_ok=True)
        with open(zip_path, "wb") as f:
            f.write(test_gtfs_content)
        
        # Extract with custom name
        custom_name = "Custom Agency Name"
        dataset_path = api.extract_gtfs(zip_path, provider_name=custom_name)
        assert dataset_path is not None
        
        # Check metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1
        dataset = datasets[0]
        assert dataset.provider_name == custom_name
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_update(test_gtfs_content):
    """Test updating existing provider's dataset."""
    test_dir = Path("test_external_update")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create initial GTFS file
        test_dir.mkdir(exist_ok=True)
        zip_path1 = test_dir / "test1.zip"
        with open(zip_path1, "wb") as f:
            f.write(test_gtfs_content)
        
        # Initial extraction
        dataset_path1 = api.extract_gtfs(zip_path1)
        assert dataset_path1 is not None
        provider_id = api.list_downloaded_datasets()[0].provider_id
        
        # Create updated GTFS file
        zip_path2 = test_dir / "test2.zip"
        with open(zip_path2, "wb") as f:
            f.write(test_gtfs_content)
        
        # Update using provider_id
        dataset_path2 = api.extract_gtfs(zip_path2, provider_id=provider_id)
        assert dataset_path2 is not None
        assert dataset_path2 != dataset_path1
        assert not dataset_path1.exists()  # Old dataset should be deleted
        
        # Check metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1  # Should still have only one dataset
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_invalid_zip():
    """Test handling of invalid ZIP files."""
    test_dir = Path("test_external_invalid")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create an invalid ZIP file
        test_dir.mkdir(exist_ok=True)
        zip_path = test_dir / "invalid.zip"
        with open(zip_path, "wb") as f:
            f.write(b"This is not a ZIP file")
        
        # Try to extract
        dataset_path = api.extract_gtfs(zip_path)
        assert dataset_path is None
        
        # Check no datasets were created
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 0
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_missing_agency():
    """Test handling of GTFS files without agency.txt."""
    test_dir = Path("test_external_no_agency")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create a GTFS file without agency.txt
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('stops.txt', 'stop_id,stop_name\n1,Test Stop')
        
        # Save the ZIP file
        test_dir.mkdir(exist_ok=True)
        zip_path = test_dir / "test.zip"
        with open(zip_path, "wb") as f:
            f.write(zip_buffer.getvalue())
        
        # Extract the GTFS file
        dataset_path = api.extract_gtfs(zip_path)
        assert dataset_path is not None
        
        # Check metadata
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 1
        dataset = datasets[0]
        assert dataset.provider_name == "Unknown Provider"
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_same_content():
    """Test handling of same content with different names."""
    test_dir = Path("test_external_same")
    api = ExternalGTFSAPI(data_dir=str(test_dir))
    
    try:
        # Create a GTFS file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('agency.txt', 
                'agency_id,agency_name,agency_url,agency_timezone\n'
                '1,Test Agency,http://test.com,Europe/London'
            )
        content = zip_buffer.getvalue()
        
        # Save as two different files
        test_dir.mkdir(exist_ok=True)
        zip_path1 = test_dir / "test1.zip"
        zip_path2 = test_dir / "test2.zip"
        with open(zip_path1, "wb") as f:
            f.write(content)
        with open(zip_path2, "wb") as f:
            f.write(content)
        
        # Extract with different names
        dataset_path1 = api.extract_gtfs(zip_path1, provider_name="Name One")
        dataset_path2 = api.extract_gtfs(zip_path2, provider_name="Name Two")
        
        # Should create two different providers due to different names
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 2
        assert datasets[0].provider_id != datasets[1].provider_id
        
        # Extract again with same name - should update existing
        dataset_path3 = api.extract_gtfs(zip_path1, provider_name="Name One")
        datasets = api.list_downloaded_datasets()
        assert len(datasets) == 2  # Still two datasets
        assert not dataset_path1.exists()  # Old dataset should be deleted
        assert dataset_path3.exists()  # New dataset should exist
        
    finally:
        if test_dir.exists():
            shutil.rmtree(test_dir)

def test_extract_gtfs_custom_dir(test_gtfs_content):
    """Test extraction to custom directory."""
    base_dir = Path("test_external_base")
    custom_dir = Path("test_external_custom")
    api = ExternalGTFSAPI(data_dir=str(base_dir))
    
    try:
        # Create directories
        base_dir.mkdir(exist_ok=True)
        custom_dir.mkdir(exist_ok=True)
        
        # Create a GTFS file
        zip_path = base_dir / "test.zip"
        with open(zip_path, "wb") as f:
            f.write(test_gtfs_content)
        
        # Extract to custom directory
        dataset_path = api.extract_gtfs(zip_path, download_dir=str(custom_dir))
        assert dataset_path is not None
        assert str(dataset_path).startswith(str(custom_dir))
        assert dataset_path.exists()
        
        # Check metadata file locations
        assert (custom_dir / "datasets_metadata.json").exists()
        assert not (base_dir / "datasets_metadata.json").exists()
        
    finally:
        if base_dir.exists():
            shutil.rmtree(base_dir)
        if custom_dir.exists():
            shutil.rmtree(custom_dir) 