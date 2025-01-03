"""
Example script demonstrating the bounding box functionality.

This script shows how to:
1. Download a dataset and get its bounding box from the API/CSV catalog
2. Process an external GTFS file and calculate its bounding box
3. Compare coverage areas of different datasets
"""

from mobility_db_api import MobilityAPI, ExternalGTFSAPI
from pathlib import Path


def print_coverage_area(dataset):
    """Helper function to print dataset coverage area."""
    print(f"\nDataset: {dataset.provider_name}")
    if dataset.minimum_latitude is not None:
        print(f"Coverage area: ({dataset.minimum_latitude}, {dataset.minimum_longitude}) to "
              f"({dataset.maximum_latitude}, {dataset.maximum_longitude})")
    else:
        print("No coverage area information available")


def main():
    # Initialize clients
    api = MobilityAPI()
    external_api = ExternalGTFSAPI()

    # Example 1: Download a dataset from Mobility Database
    print("Example 1: Dataset from Mobility Database")
    dataset_path = api.download_latest_dataset("mdb-123")
    if dataset_path:
        datasets = api.list_downloaded_datasets()
        if datasets:
            print_coverage_area(datasets[0])

    # Example 2: Process an external GTFS file
    print("\nExample 2: External GTFS file")
    external_path = Path("my_gtfs.zip")
    if external_path.exists():
        dataset_path = external_api.extract_gtfs(external_path)
        if dataset_path:
            datasets = external_api.list_downloaded_datasets()
            if datasets:
                print_coverage_area(datasets[0])

    # Example 3: Compare coverage areas
    print("\nExample 3: Coverage area comparison")
    # Get all providers in Hungary
    providers = api.get_providers_by_country("HU")
    
    # Download and compare their coverage areas
    for provider in providers[:3]:  # Limit to first 3 for example
        provider_id = provider["id"]
        dataset_path = api.download_latest_dataset(provider_id)
        if dataset_path:
            datasets = api.list_downloaded_datasets()
            for dataset in datasets:
                if dataset.provider_id == provider_id:
                    print_coverage_area(dataset)
                    break


if __name__ == "__main__":
    main() 