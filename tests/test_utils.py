import pytest
from pathlib import Path
import shutil
from mobility_db_api.utils import calculate_bounding_box

@pytest.fixture
def test_gtfs_dir():
    """Create a temporary directory for GTFS test files."""
    test_dir = Path("test_gtfs_utils")
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir)

def test_valid_stops_txt(test_gtfs_dir):
    """Test bounding box calculation with valid stops.txt."""
    stops_content = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "1,Stop 1,47.1234,-122.4567\n"
        "2,Stop 2,47.5678,-122.6789\n"
        "3,Stop 3,47.9012,-122.8901"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat == 47.1234
    assert max_lat == 47.9012
    assert min_lon == -122.8901
    assert max_lon == -122.4567

def test_missing_stops_txt(test_gtfs_dir):
    """Test handling of missing stops.txt."""
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat is None
    assert max_lat is None
    assert min_lon is None
    assert max_lon is None

def test_empty_stops_txt(test_gtfs_dir):
    """Test handling of empty stops.txt."""
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write("stop_id,stop_name,stop_lat,stop_lon\n")
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat is None
    assert max_lat is None
    assert min_lon is None
    assert max_lon is None

def test_missing_coordinate_fields(test_gtfs_dir):
    """Test handling of stops.txt without coordinate fields."""
    stops_content = (
        "stop_id,stop_name\n"
        "1,Stop 1\n"
        "2,Stop 2"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat is None
    assert max_lat is None
    assert min_lon is None
    assert max_lon is None

def test_invalid_coordinates(test_gtfs_dir):
    """Test handling of invalid coordinate values."""
    stops_content = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "1,Stop 1,47.1234,-122.4567\n"
        "2,Invalid,not_a_number,-122.6789\n"
        "3,Stop 3,47.9012,-122.8901"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat == 47.1234
    assert max_lat == 47.9012
    assert min_lon == -122.8901
    assert max_lon == -122.4567

def test_out_of_range_coordinates(test_gtfs_dir):
    """Test handling of coordinates outside valid ranges."""
    stops_content = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "1,Valid,47.1234,-122.4567\n"
        "2,Invalid Lat,91.0000,-122.6789\n"
        "3,Invalid Lon,47.9012,-181.0000\n"
        "4,Valid,47.5678,-122.8901"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat == 47.1234
    assert max_lat == 47.5678
    assert min_lon == -122.8901
    assert max_lon == -122.4567

def test_boundary_coordinates(test_gtfs_dir):
    """Test handling of coordinates at boundary values."""
    stops_content = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "1,North Pole,90.0000,0.0000\n"
        "2,South Pole,-90.0000,0.0000\n"
        "3,Date Line West,0.0000,-180.0000\n"
        "4,Date Line East,0.0000,180.0000"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat == -90.0000
    assert max_lat == 90.0000
    assert min_lon == -180.0000
    assert max_lon == 180.0000

def test_missing_bounding_box_fields(test_gtfs_dir):
    """Test handling of stops.txt with missing bounding box fields."""
    stops_content = (
        "stop_id,stop_name,stop_lat\n"  # Missing stop_lon
        "1,Stop 1,47.1234\n"
        "2,Stop 2,47.5678"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat is None
    assert max_lat is None
    assert min_lon is None
    assert max_lon is None

def test_malformed_stops_txt(test_gtfs_dir):
    """Test handling of malformed stops.txt."""
    stops_content = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "1,Stop 1,47.1234\n"  # Missing stop_lon value
        "2,Stop 2,47.5678,-122.6789"
    )
    with open(test_gtfs_dir / "stops.txt", "w") as f:
        f.write(stops_content)
    
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(test_gtfs_dir)
    assert min_lat == 47.5678
    assert max_lat == 47.5678
    assert min_lon == -122.6789
    assert max_lon == -122.6789 