import requests
import json

def test_api():
    base_url = "http://127.0.0.1:5000/api"
    filepath = r"c:\Users\NDOUR\Desktop\data\property data.csv"
    
    # 1. Get Guest Token
    print("--- Getting Token ---")
    resp = requests.post(f"{base_url}/auth/guest")
    token = resp.json().get('token')
    headers = {'Authorization': f'Bearer {token}'}
    
    # 2. Upload File
    print("--- Uploading File ---")
    with open(filepath, 'rb') as f:
        files = {'file': ('property data.csv', f, 'text/csv')}
        upload_resp = requests.post(f"{base_url}/datasets/upload", headers=headers, files=files)
    
    if upload_resp.status_code != 200:
        print("Upload failed:", upload_resp.text)
        return
        
    dataset_id = upload_resp.json().get('dataset_id')
    print("Dataset ID:", dataset_id)
    
    # 3. Call Autopilot
    print("--- Calling Autopilot ---")
    auto_resp = requests.post(f"{base_url}/datasets/{dataset_id}/autopilot", headers=headers)
    print("Status:", auto_resp.status_code)
    try:
        print("Response:", json.dumps(auto_resp.json(), indent=2))
    except:
        print("Response:", auto_resp.text)

if __name__ == "__main__":
    test_api()
