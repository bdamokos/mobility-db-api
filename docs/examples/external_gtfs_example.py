from mobility_db_api import ExternalGTFSAPI
from pathlib import Path

def print_dataset_info(dataset):
    """Print relevant information about a dataset"""
    print(f"Provider: {dataset.provider_name} ({dataset.provider_id})")
    print(f"Dataset: {dataset.dataset_id}")
    print(f"Downloaded: {dataset.download_date}")
    print(f"Path: {dataset.download_path}")
    if dataset.feed_start_date and dataset.feed_end_date:
        print(f"Feed validity: {dataset.feed_start_date} to {dataset.feed_end_date}")
    print()

def main():
    # Initialize API
    api = ExternalGTFSAPI()
    
    # Example 1: Extract GTFS with automatic provider ID and name
    print("\n=== Example 1: Automatic provider ID and name ===")
    dataset_path = api.extract_gtfs(
        zip_path=Path("gtfs_files/agency1.zip")
    )
    if dataset_path:
        print(f"Dataset extracted to: {dataset_path}")
        
    # Example 2: Extract with specific provider name
    print("\n=== Example 2: Specific provider name ===")
    dataset_path = api.extract_gtfs(
        zip_path=Path("gtfs_files/agency2.zip"),
        provider_name="My Transit Agency"
    )
    if dataset_path:
        print(f"Dataset extracted to: {dataset_path}")
    
    # Example 3: Update existing provider's dataset
    print("\n=== Example 3: Update existing dataset ===")
    dataset_path = api.extract_gtfs(
        zip_path=Path("gtfs_files/agency1_updated.zip"),
        provider_id="ext-1"  # Use the ID from Example 1
    )
    if dataset_path:
        print(f"Dataset updated at: {dataset_path}")
    
    # Example 4: List all datasets
    print("\n=== Example 4: List all datasets ===")
    datasets = api.list_downloaded_datasets()
    print(f"Found {len(datasets)} datasets:")
    for dataset in datasets:
        print_dataset_info(dataset)
    
    # Example 5: Delete a specific dataset
    print("\n=== Example 5: Delete dataset ===")
    if datasets:
        first_dataset = datasets[0]
        api.delete_dataset(first_dataset.provider_id, first_dataset.dataset_id)
        print(f"Deleted dataset: {first_dataset.dataset_id}")

if __name__ == "__main__":
    main() 