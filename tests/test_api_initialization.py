import pytest
import tempfile
import shutil
from pathlib import Path
import multiprocessing
import time
import json
import threading
from datetime import datetime
from mobility_db_api.api import MobilityAPI, MetadataLock, DatasetMetadata

def create_api_and_write_marker(data_dir: str, marker_value: str):
    """Helper function for multiprocessing test"""
    api = MobilityAPI(data_dir=data_dir)
    # Write a marker file to prove this process created its own instance
    marker_path = Path(data_dir) / f"process_marker_{marker_value}.txt"
    with open(marker_path, "w") as f:
        f.write(f"Process {marker_value} was here")
    # Sleep briefly to ensure both processes can run
    time.sleep(0.5)

def write_metadata_process(data_dir: str, dataset_id: str, delay: float = 0):
    """Helper function to write metadata from a separate process"""
    time.sleep(delay)  # Optional delay to control timing
    api = MobilityAPI(data_dir=data_dir)
    
    # Create test metadata
    download_path = Path(data_dir) / f"test_dataset_{dataset_id}"
    metadata = DatasetMetadata(
        provider_id="test",
        provider_name="Test Provider",
        dataset_id=dataset_id,
        download_date=datetime.fromisoformat("2024-01-01T00:00:00"),
        source_url="http://test.com",
        is_direct_source=False,
        api_provided_hash=None,
        file_hash="abc123",
        download_path=download_path
    )
    
    # Add to API's datasets and save
    api.datasets[f"test_dataset_{dataset_id}"] = metadata
    api._save_metadata()  # This will merge with existing metadata

def read_metadata_process(data_dir: str):
    """Helper function to read metadata from a separate process"""
    api = MobilityAPI(data_dir=data_dir)
    api.reload_metadata(force=True)

@pytest.fixture
def test_dirs():
    """Create temporary test directories and clean up after"""
    test_dir = tempfile.mkdtemp()
    data_dir1 = str(Path(test_dir) / "data1")
    data_dir2 = str(Path(test_dir) / "data2")
    
    yield {
        "test_dir": test_dir,
        "data_dir1": data_dir1,
        "data_dir2": data_dir2
    }
    
    # Clean up after test
    shutil.rmtree(test_dir)

def test_multiple_calls_same_directory(test_dirs):
    """Test that multiple instances can share the same directory"""
    api1 = MobilityAPI(data_dir=test_dirs["data_dir1"], logger_name="test_logger1")
    api2 = MobilityAPI(data_dir=test_dirs["data_dir1"], logger_name="test_logger2")
    
    # Verify both instances use the same directory
    assert api1.data_dir == api2.data_dir
    
    # Verify both instances have separate logger instances
    assert api1.logger is not api2.logger

def test_metadata_sharing(test_dirs):
    """Test that metadata is properly shared between instances"""
    # Create first instance
    api1 = MobilityAPI(data_dir=test_dirs["data_dir1"], logger_name="test_logger1")
    metadata_file = Path(test_dirs["data_dir1"]) / "datasets_metadata.json"
    
    # Write test metadata
    test_metadata = {
        "test_dataset": {
            "provider_id": "test",
            "provider_name": "Test Provider",
            "dataset_id": "test_123",
            "download_date": "2024-01-01T00:00:00",
            "source_url": "http://test.com",
            "is_direct_source": False,
            "api_provided_hash": None,
            "file_hash": "abc123",
            "download_path": str(Path(test_dirs["data_dir1"]) / "test_dataset")
        }
    }
    with open(metadata_file, "w") as f:
        json.dump(test_metadata, f)
    
    # Reload metadata in first instance
    api1.reload_metadata()  # Using the new reload_metadata method
    
    # Create second instance and verify it loads the metadata
    api2 = MobilityAPI(data_dir=test_dirs["data_dir1"], logger_name="test_logger2")
    
    # Verify metadata is loaded in both instances
    assert len(api1.datasets) == 1
    assert len(api2.datasets) == 1
    assert api1.datasets["test_dataset"].dataset_id == "test_123"
    assert api2.datasets["test_dataset"].dataset_id == "test_123"

def test_different_data_directories(test_dirs):
    """Test that two instances can have different data directories"""
    api1 = MobilityAPI(data_dir=test_dirs["data_dir1"])
    api2 = MobilityAPI(data_dir=test_dirs["data_dir2"])

    # Verify directories are different
    assert api1.data_dir != api2.data_dir
    
    # Verify both directories were created
    assert Path(test_dirs["data_dir1"]).exists()
    assert Path(test_dirs["data_dir2"]).exists()
    
    # Verify separate metadata files
    assert api1.metadata_file != api2.metadata_file

def test_multiprocess_same_directory(test_dirs):
    """Test that two processes can create separate instances with same directory"""
    # Create two processes that will each create an API instance
    p1 = multiprocessing.Process(
        target=create_api_and_write_marker,
        args=(test_dirs["data_dir1"], "1")
    )
    p2 = multiprocessing.Process(
        target=create_api_and_write_marker,
        args=(test_dirs["data_dir1"], "2")
    )

    # Start both processes
    p1.start()
    p2.start()

    # Wait for both processes to complete
    p1.join()
    p2.join()

    # Verify both processes created their markers
    marker1 = Path(test_dirs["data_dir1"]) / "process_marker_1.txt"
    marker2 = Path(test_dirs["data_dir1"]) / "process_marker_2.txt"
    
    assert marker1.exists()
    assert marker2.exists()
    
    # Verify the content of markers
    with open(marker1) as f:
        assert f.read() == "Process 1 was here"
    with open(marker2) as f:
        assert f.read() == "Process 2 was here" 

def test_file_locking(test_dirs):
    """Test that file locking prevents concurrent writes"""
    data_dir = test_dirs["data_dir1"]
    metadata_file = Path(data_dir) / "datasets_metadata.json"
    
    # Create two processes that will try to write metadata simultaneously
    p1 = multiprocessing.Process(
        target=write_metadata_process,
        args=(data_dir, "1")
    )
    p2 = multiprocessing.Process(
        target=write_metadata_process,
        args=(data_dir, "2", 0.1)  # Small delay to ensure overlap
    )
    
    # Start both processes
    p1.start()
    p2.start()
    
    # Wait for both processes to complete
    p1.join()
    p2.join()
    
    # Read the final metadata
    api = MobilityAPI(data_dir=data_dir)
    
    # The metadata should contain both datasets, proving that no write was lost
    assert len(api.datasets) == 2
    assert "test_dataset_1" in api.datasets
    assert "test_dataset_2" in api.datasets

def test_metadata_change_detection(test_dirs):
    """Test that the API detects and reloads changed metadata"""
    data_dir = test_dirs["data_dir1"]
    
    # Create first instance and initial metadata
    api1 = MobilityAPI(data_dir=data_dir)
    write_metadata_process(data_dir, "1")
    
    # Force reload and verify initial state
    assert api1.reload_metadata(force=True)
    assert len(api1.datasets) == 1
    assert "test_dataset_1" in api1.datasets
    
    # Write new metadata from a different process
    write_metadata_process(data_dir, "2")
    
    # Check if change is detected
    assert api1._has_metadata_changed()
    
    # Ensure metadata is current and verify both datasets are present
    assert api1.ensure_metadata_current()
    assert len(api1.datasets) == 2
    assert "test_dataset_1" in api1.datasets
    assert "test_dataset_2" in api1.datasets

def test_lock_cleanup(test_dirs):
    """Test that file locks are properly released"""
    data_dir = test_dirs["data_dir1"]
    metadata_file = Path(data_dir) / "datasets_metadata.json"
    
    def try_write_lock():
        """Try to acquire a write lock"""
        try:
            with MetadataLock(metadata_file, 'w') as f:
                f.write("{}")
            return True
        except:
            return False
    
    # First, create a file with some content
    write_metadata_process(data_dir, "1")
    
    # Create an API instance and force it to load metadata
    api = MobilityAPI(data_dir=data_dir)
    api.reload_metadata(force=True)
    
    # We should be able to acquire a write lock immediately after
    assert try_write_lock()

def test_concurrent_reads(test_dirs):
    """Test that multiple processes can read metadata simultaneously"""
    data_dir = test_dirs["data_dir1"]
    
    # Create initial metadata
    write_metadata_process(data_dir, "1")
    
    # Create multiple processes that will read simultaneously
    processes = []
    for i in range(5):  # Try with 5 concurrent readers
        p = multiprocessing.Process(
            target=read_metadata_process,
            args=(data_dir,)
        )
        processes.append(p)
    
    # Start all processes
    for p in processes:
        p.start()
    
    # Wait for all processes to complete
    for p in processes:
        p.join()
        assert p.exitcode == 0  # Verify each process completed successfully 