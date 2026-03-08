import requests
import os

def check_export():
    dataset_id = "8d573847-f958-481f-9d19-81b620d306e4"
    url = f"http://localhost:5000/api/datasets/{dataset_id}/export?format=csv"
    
    r = requests.get(url)
    print(f"Status: {r.status_code}")
    print(f"Headers: {r.headers}")
    print(f"Content Length: {len(r.content)}")
    print("\nContent Preview:")
    print(r.text)
    
    with open("export_test.csv", "wb") as f:
        f.write(r.content)

if __name__ == "__main__":
    check_export()
