import os
import pytest
from mobility_db_api import MobilityAPI

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