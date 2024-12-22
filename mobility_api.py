import os
import requests
from dotenv import load_dotenv
import json
from typing import Optional, Dict, Any, List

# Load environment variables
load_dotenv()

class MobilityAPI:
    def __init__(self):
        self.base_url = "https://api.mobilitydatabase.org"
        self.refresh_token = os.getenv("MOBILITY_API_REFRESH_TOKEN")
        if not self.refresh_token:
            raise ValueError("Refresh token not found in .env file")
        print(f"Refresh token loaded: {self.refresh_token[:20]}...")
        self.access_token = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Get initial access token
        if not self.get_access_token():
            raise ValueError("Failed to get initial access token")

    def get_access_token(self) -> bool:
        """Get a new access token using the refresh token"""
        print("\nGetting access token...")
        url = f"{self.base_url}/v1/tokens"
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"refresh_token": self.refresh_token}
            )
            print(f"Token request status code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                if self.access_token:
                    print(f"Got access token: {self.access_token[:20]}...")
                    self.headers["Authorization"] = f"Bearer {self.access_token}"
                    return True
                else:
                    print("No access token in response")
                    print(f"Response data: {data}")
                    return False
            else:
                print(f"Failed to get access token: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        except Exception as e:
            print(f"Exception during token request: {str(e)}")
            return False

    def get_gtfs_feeds(self, limit: int = 100, offset: int = 0) -> Optional[List[Dict[str, Any]]]:
        """Get list of GTFS feeds"""
        print("\nGetting GTFS feeds...")
        url = f"{self.base_url}/v1/gtfs_feeds"
        params = {
            "limit": limit,
            "offset": offset
        }
        try:
            response = requests.get(url, headers=self.headers, params=params)
            print(f"GTFS feeds request status code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else data.get('feeds', [])
            elif response.status_code == 401:
                print("Unauthorized. Trying to refresh token...")
                if self.get_access_token():
                    return self.get_gtfs_feeds(limit, offset)
            print(f"GTFS feeds request failed. Response: {response.text}")
            return None
        except Exception as e:
            print(f"Exception during GTFS feeds request: {str(e)}")
            return None

    def get_gtfs_feed(self, feed_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific GTFS feed"""
        print(f"\nGetting GTFS feed {feed_id}...")
        url = f"{self.base_url}/v1/gtfs_feeds/{feed_id}"
        try:
            response = requests.get(url, headers=self.headers)
            print(f"GTFS feed request status code: {response.status_code}")
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("Unauthorized. Trying to refresh token...")
                if self.get_access_token():
                    return self.get_gtfs_feed(feed_id)
            print(f"GTFS feed request failed. Response: {response.text}")
            return None
        except Exception as e:
            print(f"Exception during GTFS feed request: {str(e)}")
            return None

    def get_gtfs_datasets(self, feed_id: str, latest: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Get datasets for a GTFS feed"""
        print(f"\nGetting datasets for GTFS feed {feed_id}...")
        url = f"{self.base_url}/v1/gtfs_feeds/{feed_id}/datasets"
        params = {
            "latest": latest
        }
        try:
            response = requests.get(url, headers=self.headers, params=params)
            print(f"Datasets request status code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else data.get('datasets', [])
            elif response.status_code == 401:
                print("Unauthorized. Trying to refresh token...")
                if self.get_access_token():
                    return self.get_gtfs_datasets(feed_id, latest)
            print(f"Datasets request failed. Response: {response.text}")
            return None
        except Exception as e:
            print(f"Exception during datasets request: {str(e)}")
            return None

    @staticmethod
    def get_auth_type_description(auth_type: Optional[int]) -> str:
        """Get a human-readable description of the authentication type"""
        auth_types = {
            0: "No authentication required",
            1: "Username/password required",
            2: "API key required",
            3: "OAuth required",
            4: "Other authentication method"
        }
        return auth_types.get(auth_type, "Unknown authentication type")

if __name__ == "__main__":
    try:
        api = MobilityAPI()
        
        # Get GTFS feeds
        feeds = api.get_gtfs_feeds()
        if feeds:
            print(f"\nFound {len(feeds)} GTFS Schedule feeds:")
            
            # Count feeds by authentication type
            auth_type_counts = {}
            
            for feed in feeds:
                print(f"\nFeed: {feed.get('name', 'Unknown')}")
                print(f"ID: {feed.get('id')}")
                print(f"Provider: {feed.get('provider', 'Unknown')}")
                
                # Get the latest dataset for this feed
                datasets = api.get_gtfs_datasets(feed.get('id'), latest=True)
                if datasets:
                    for dataset in datasets:
                        auth_type = dataset.get('authentication_type')
                        auth_type_counts[auth_type] = auth_type_counts.get(auth_type, 0) + 1
                        
                        print("Dataset:")
                        print(f"  ID: {dataset.get('id')}")
                        print(f"  Authentication: {api.get_auth_type_description(auth_type)}")
                        if auth_type == 0:  # No authentication required
                            print(f"  Direct download URL: {dataset.get('direct_download_url')}")
                        else:
                            print(f"  Authentication required - use API endpoints for download")
                else:
                    print("No datasets available")
            
            # Print summary
            print("\nSummary of authentication types:")
            for auth_type, count in sorted(auth_type_counts.items()):
                print(f"{api.get_auth_type_description(auth_type)}: {count} feeds")
        else:
            print("Failed to get GTFS feeds list")
    except Exception as e:
        print(f"Error: {str(e)}")