
import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_export_formats():
    # 1. Login to get a Starter token
    # (Assuming the user 'starter@test.com' exists and has 'starter' tier)
    # If not, we can use the register route or look for an existing user.
    
    # For testing purposes, we can also simulate the JWT if we have the secret, 
    # but it's better to use the actual API.
    
    print("--- Testing Export Formats ---")
    
    # Try to find a dataset and test guest export first
    datasets = requests.get(f"{BASE_URL}/datasets/").json() # Might need auth
    
    # If we don't have a dataset, we skip for now or use a dummy ID
    dataset_id = "dummy_id" # Replace with real ID if possible
    
    formats = ["csv", "xlsx", "json", "xml"]
    
    for fmt in formats:
        print(f"Testing format: {fmt} (Guest)")
        res = requests.get(f"{BASE_URL}/datasets/{dataset_id}/export", params={"format": fmt})
        if res.status_code == 403:
            data = res.json()
            print(f"  Result: BLOCKED (403) - Trigger: {data.get('trigger')} - Tier: {data.get('current_tier')}")
        elif res.status_code == 200:
            print(f"  Result: SUCCESS (200)")
        else:
            print(f"  Result: ERROR ({res.status_code})")

if __name__ == "__main__":
    # Note: This script requires a running server and valid dataset_id
    print("Verification script ready.")
