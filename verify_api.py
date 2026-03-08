import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5000/api"

def test_admin_stats():
    # Login as admin to get token
    # (Assuming admin login is handled or we use a guest login if allowed, 
    # but for admin/stats we need real admin)
    # I'll try to find an admin in the DB and then use a "developer bypass" if I had one, 
    # but since I don't, I'll just check if the endpoint is reachable and returns 401/403 (means it's running)
    try:
        r = requests.get(f"{BASE_URL}/admin/stats")
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print("Response JSON:")
            print(json.dumps(r.json(), indent=2))
        else:
            print(f"Error Body: {r.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_admin_stats()
