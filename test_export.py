import requests
import os
import pandas as pd

API_URL = "http://127.0.0.1:5000/api/datasets"

def test_exports():
    # 1. Upload a dummy file to get a dataset_id
    df = pd.DataFrame({'a': [1, 2], 'b': ['x', 'y']})
    df.to_csv("test_temp.csv", index=False)
    
    with open("test_temp.csv", "rb") as f:
        r = requests.post(f"{API_URL}/upload", files={'file': f})
    
    if r.status_code != 200:
        print(f"Upload failed: {r.text}")
        return
    
    dataset_id = r.json().get('dataset_id') or r.json().get('id')
    print(f"Dataset ID: {dataset_id}")

    formats = ['csv', 'json', 'excel', 'xml']
    for fmt in formats:
        print(f"Testing format: {fmt}")
        r = requests.get(f"{API_URL}/{dataset_id}/export?format={fmt}")
        if r.status_code == 200:
            content_type = r.headers.get('Content-Type')
            content_length = len(r.content)
            print(f"  [PASS] {fmt} exported successfully. Size: {content_length}, Content-Type: {content_type}")
            
            # Save for manual check if needed
            ext = 'xlsx' if fmt == 'excel' else fmt
            with open(f"test_export_{dataset_id}.{ext}", "wb") as f_out:
                f_out.write(r.content)
        else:
            print(f"  [FAIL] {fmt} export failed: {r.text}")

    # Cleanup
    if os.path.exists("test_temp.csv"): os.remove("test_temp.csv")

if __name__ == "__main__":
    test_exports()
