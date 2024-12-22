from mobility_db_api import MobilityAPI
from pprint import pprint
import os

def print_provider_info(provider: dict):
    """Print relevant information about a provider"""
    print(f"Provider: {provider.get('provider', 'Unknown')}")
    print(f"ID: {provider.get('id', 'Unknown')}")
    print(f"Status: {provider.get('status', 'Unknown')}")
    if latest := provider.get('latest_dataset'):
        print(f"Latest dataset: {latest.get('id')}")
        print(f"Last updated: {latest.get('created_at')}")
    print()

def main():
    # Initialize API with optional custom refresh token
    refresh_token = os.getenv("MOBILITY_API_REFRESH_TOKEN")  # You could also pass it directly
    api = MobilityAPI(refresh_token=refresh_token)
    
    # Test country search (Hungary)
    print("\n=== Testing providers in Hungary ===")
    hungary_providers = api.get_providers_by_country("HU")
    print(f"Found {len(hungary_providers)} providers in Hungary")
    
    if hungary_providers:
        # Take the first provider from Hungary
        first_hu_provider = hungary_providers[0]
        print("\nFirst provider from Hungary:")
        print_provider_info(first_hu_provider)
        
        # Download to default location
        print(f"\nDownloading dataset for {first_hu_provider.get('provider')}...")
        dataset_path = api.download_latest_dataset(first_hu_provider['id'])
        if dataset_path:
            print(f"Dataset downloaded to: {dataset_path}")
            print("Files in the dataset:")
            for file in dataset_path.glob("*.txt"):
                print(f"  - {file.name}")
    
    # Test name search (SNCB)
    print("\n=== Testing SNCB search ===")
    sncb_results = api.get_providers_by_name("SNCB")
    print(f"Found {len(sncb_results)} providers matching 'SNCB'")
    
    if sncb_results:
        # Take the first SNCB provider
        first_sncb = sncb_results[0]
        print("\nFirst SNCB provider:")
        print_provider_info(first_sncb)
        
        # Download to a custom location
        custom_dir = "custom_downloads"
        print(f"\nDownloading dataset for {first_sncb.get('provider')} to custom directory...")
        dataset_path = api.download_latest_dataset(first_sncb['id'], download_dir=custom_dir)
        if dataset_path:
            print(f"Dataset downloaded to: {dataset_path}")
            print("Files in the dataset:")
            for file in dataset_path.glob("*.txt"):
                print(f"  - {file.name}")

if __name__ == "__main__":
    main() 