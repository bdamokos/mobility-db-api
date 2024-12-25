"""Tests for CSV catalog functionality."""

import pytest
import tempfile
import shutil
from pathlib import Path
import responses
from mobility_db_api.csv_catalog import CSVCatalog

@pytest.fixture
def test_csv_content():
    """Sample CSV content for testing."""
    return (
        "mdb_source_id,data_type,provider,location.country_code,urls.direct_download,urls.latest,status,features,urls.license,redirect.id\n"
        "test-1,gtfs,Test Provider 1,HU,http://test1.com/direct,http://test1.com/latest,,,http://test1.com/license,\n"
        "test-2,gtfs,Test Provider 2,BE,http://test2.com/direct,http://test2.com/latest,,,http://test2.com/license,\n"
        "test-3,gtfs,Another Provider,HU,http://test3.com/direct,http://test3.com/latest,,,http://test3.com/license,\n"
        "test-4,gtfs,Inactive Provider,US,http://test4.com/direct,http://test4.com/latest,inactive,,http://test4.com/license,\n"
        "test-5,gtfs,Deprecated Provider,CA,http://test5.com/direct,http://test5.com/latest,deprecated,,http://test5.com/license,\n"
        "test-6,gtfs,Redirected Provider,FR,http://test6.com/direct,http://test6.com/latest,,,http://test6.com/license,test-1\n"
        "test-7,gbfs,Bike Share,UK,http://test7.com/direct,http://test7.com/latest,,,http://test7.com/license,\n"
    )

@pytest.fixture
def test_dir():
    """Create and clean up a test directory."""
    test_dir = tempfile.mkdtemp()
    yield test_dir
    shutil.rmtree(test_dir)

@pytest.fixture
def catalog(test_dir):
    """Create a CSVCatalog instance with test directory."""
    return CSVCatalog(cache_dir=test_dir)

def test_init(catalog, test_dir):
    """Test CSVCatalog initialization."""
    assert catalog.cache_dir == Path(test_dir)
    assert catalog.csv_path == Path(test_dir) / "mobility_catalog.csv"
    assert catalog._providers is None

@responses.activate
def test_download_csv(catalog, test_csv_content):
    """Test CSV download functionality."""
    # Mock the CSV download
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=test_csv_content,
        status=200
    )
    
    # Test successful download
    assert catalog._download_csv(force=True) is True
    assert catalog.csv_path.exists()
    with open(catalog.csv_path, 'r') as f:
        assert f.read() == test_csv_content
    
    # Test failed download with force
    responses.replace(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        status=404
    )
    assert catalog._download_csv(force=True) is False
    
    # Test cached response (should return True without making request)
    assert catalog._download_csv() is True

@responses.activate
def test_load_providers(catalog, test_csv_content):
    """Test provider loading from CSV."""
    # Mock the CSV download
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=test_csv_content,
        status=200
    )
    
    providers = catalog._load_providers()
    # Should only include active GTFS providers (test-1, test-2, test-3)
    assert len(providers) == 3
    
    # Check first provider
    provider = providers[0]
    assert provider['id'] == 'test-1'
    assert provider['provider'] == 'Test Provider 1'
    assert provider['country'] == 'HU'
    assert provider['source_info']['producer_url'] == 'http://test1.com/direct'
    assert provider['latest_dataset']['hosted_url'] == 'http://test1.com/latest'
    assert provider['license_url'] == 'http://test1.com/license'
    assert provider['data_type'] == 'gtfs'
    assert provider['status'] == ''

@responses.activate
def test_provider_filtering(catalog, test_csv_content):
    """Test that providers are properly filtered."""
    # Mock the CSV download
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=test_csv_content,
        status=200
    )
    
    providers = catalog._load_providers()
    provider_ids = {p['id'] for p in providers}
    
    # Check that only active GTFS providers are included
    assert 'test-1' in provider_ids  # Active GTFS
    assert 'test-2' in provider_ids  # Active GTFS
    assert 'test-3' in provider_ids  # Active GTFS
    assert 'test-4' not in provider_ids  # Inactive
    assert 'test-5' not in provider_ids  # Deprecated
    assert 'test-6' not in provider_ids  # Redirected
    assert 'test-7' not in provider_ids  # GBFS (not GTFS)

@responses.activate
def test_get_providers_by_country(catalog, test_csv_content):
    """Test searching providers by country."""
    # Mock the CSV download
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=test_csv_content,
        status=200
    )
    
    # Test case-insensitive search
    hu_providers = catalog.get_providers_by_country('hu')
    assert len(hu_providers) == 2
    assert hu_providers[0]['id'] == 'test-1'
    assert hu_providers[1]['id'] == 'test-3'
    
    # Test non-existent country
    assert len(catalog.get_providers_by_country('XX')) == 0
    
    # Test country with only inactive/deprecated providers
    assert len(catalog.get_providers_by_country('US')) == 0

@responses.activate
def test_get_providers_by_name(catalog, test_csv_content):
    """Test searching providers by name."""
    # Mock the CSV download
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=test_csv_content,
        status=200
    )
    
    # Test partial match (should only include active GTFS providers)
    test_providers = catalog.get_providers_by_name('Test')
    assert len(test_providers) == 2
    assert test_providers[0]['id'] == 'test-1'
    assert test_providers[1]['id'] == 'test-2'
    
    # Test case-insensitive search
    providers = catalog.get_providers_by_name('provider')
    assert len(providers) == 3  # Only active GTFS providers
    
    # Test non-existent name
    assert len(catalog.get_providers_by_name('NonExistent')) == 0
    
    # Test searching for inactive/deprecated providers (should return none)
    assert len(catalog.get_providers_by_name('Inactive')) == 0
    assert len(catalog.get_providers_by_name('Deprecated')) == 0

@responses.activate
def test_provider_caching(catalog, test_csv_content):
    """Test that providers are properly cached."""
    # Mock the CSV download
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=test_csv_content,
        status=200
    )
    
    # First call should download and cache
    providers1 = catalog.get_providers()
    assert len(providers1) == 3  # Only active GTFS providers
    
    # Change the mock response with different but valid data
    new_content = (
        "mdb_source_id,data_type,provider,location.country_code,urls.direct_download,urls.latest,status,features,urls.license,redirect.id\n"
        "test-8,gtfs,New Provider 1,DE,http://test8.com/direct,http://test8.com/latest,,,http://test8.com/license,\n"
        "test-9,gtfs,New Provider 2,FR,http://test9.com/direct,http://test9.com/latest,,,http://test9.com/license,\n"
    )
    
    # Remove the old mock and add a new one
    responses.remove(responses.GET, CSVCatalog.CATALOG_URL)
    responses.add(
        responses.GET,
        CSVCatalog.CATALOG_URL,
        body=new_content,
        status=200
    )
    
    # Second call should use cache
    providers2 = catalog.get_providers()
    assert providers2 == providers1
    
    # Force reload should download again and get new data
    providers3 = catalog.get_providers(force_reload=True)
    assert providers3 != providers1
    assert len(providers3) == 2  # New data has 2 active GTFS providers
    assert providers3[0]['id'] == 'test-8'
    assert providers3[1]['id'] == 'test-9' 