import requests
import json
import os

BASE_URL = "http://localhost:5000/api/datasets"

def test_routes():
    res = []
    def log(msg):
        print(msg)
        res.append(msg)

    # 1. Upload
    log("--- Testing Upload ---")
    csv_content = "A,B,C\n1,2,3\n4,5,6\n1,2,3" # Includes a duplicate
    with open("verify_data.csv", "w") as f:
        f.write(csv_content)
    
    try:
        with open("verify_data.csv", "rb") as f:
            files = {'file': ('verify_data.csv', f, 'text/csv')}
            data = {'id': 'verify_id'}
            r = requests.post(f"{BASE_URL}/upload", files=files, data=data)
        
        if r.status_code != 200:
            log(f"Upload failed: {r.text}")
            return
        
        log("Upload Success")
        
        # 2. Autopilot
        log("\n--- Testing Autopilot ---")
        r = requests.post(f"{BASE_URL}/verify_id/autopilot")
        if r.status_code != 200:
            log(f"Autopilot failed: {r.text}")
        else:
            resp = r.json()
            log(f"Autopilot Success. Has columnInfo: {'columnInfo' in resp}")
            if 'columnInfo' in resp:
                log(f"Number of columns: {len(resp['columnInfo'])}")
        
        # 3. Process (Manual Transformation)
        log("\n--- Testing Process (Manual) ---")
        payload = {
            "type": "remove_duplicates",
            "params": {}
        }
        r = requests.post(f"{BASE_URL}/verify_id/process", json=payload)
        if r.status_code != 200:
            log(f"Process failed: {r.text}")
        else:
            resp = r.json()
            log(f"Process Success. Has columnInfo: {'columnInfo' in resp}")
            if 'columnInfo' in resp:
                log(f"Number of columns: {len(resp['columnInfo'])}")

    except Exception as e:
        log(f"Error during testing: {str(e)}")

    with open("verify_res.txt", "w") as f:
        f.write("\n".join(res))

if __name__ == "__main__":
    test_routes()
