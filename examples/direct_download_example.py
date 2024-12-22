from mobility_db_api import MobilityAPI
from pathlib import Path
import json
import shutil

def print_metadata(metadata_file: Path):
    """Print the contents of a metadata file"""
    if metadata_file.exists():
        print(f"\nMetadata from {metadata_file}:")
        with open(metadata_file, 'r') as f:
            data = json.load(f)
            for key, item in data.items():
                print(f"\nDataset: {key}")
                print(f"Provider: {item['provider_name']}")
                print(f"Source: {'Direct' if item['is_direct_source'] else 'Hosted'}")
                print(f"Download path: {item['download_path']}")
                if item.get('feed_start_date'):
                    print(f"Feed validity: {item['feed_start_date']} to {item['feed_end_date']}")
    else:
        print(f"\nNo metadata file found at {metadata_file}")

def main():
    # Clean up any existing test directories
    test_dirs = ['test_downloads', 'test_downloads_direct']
    for dir_name in test_dirs:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
    
    # Initialize API
    api = MobilityAPI()
    
    # Test 1: Download SNCB dataset using hosted URL
    print("\n=== Test 1: Hosted URL Download ===")
    sncb_results = api.get_providers_by_name("SNCB")
    if sncb_results:
        sncb = sncb_results[0]
        print(f"Downloading {sncb['provider']} dataset to test_downloads...")
        dataset_path = api.download_latest_dataset(
            sncb['id'],
            download_dir='test_downloads'
        )
        if dataset_path:
            print(f"Dataset downloaded to: {dataset_path}")
    
    # Test 2: Download Volánbusz dataset using direct URL
    print("\n=== Test 2: Direct URL Download ===")
    print("Downloading Volánbusz dataset using direct URL to test_downloads_direct...")
    dataset_path = api.download_latest_dataset(
        'tld-5862',  # Volánbusz ID
        download_dir='test_downloads_direct',
        use_direct_source=True
    )
    if dataset_path:
        print(f"Dataset downloaded to: {dataset_path}")
    
    # Check metadata files
    print("\n=== Checking Metadata Files ===")
    print_metadata(Path('data/datasets_metadata.json'))  # Main metadata
    print_metadata(Path('test_downloads/datasets_metadata.json'))  # Test 1 metadata
    print_metadata(Path('test_downloads_direct/datasets_metadata.json'))  # Test 2 metadata

if __name__ == "__main__":
    main() 