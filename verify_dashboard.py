import requests
import json

BASE_URL = "http://localhost:5000/api/datasets"
DATASET_ID = "7096d4a7-c062-4bb5-a5a6-96c5cce5cb9a"

def test_route(route, params=None):
    url = f"{BASE_URL}/{DATASET_ID}/{route}"
    print(f"Testing {url} with params {params}...")
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Data keys: {list(data.keys()) if isinstance(data, dict) else 'List of ' + str(len(data))}")
            return True
        else:
            print(f"Failed: {response.text}")
            return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

routes_to_test = [
    ("types", None),
    ("quality", None),
    ("correlation", None),
    ("stats", {"column": "property_type"}), # Using a categorical col to see {}
    ("stats", {"column": "price"}), # Assuming price exists in property data.csv
    ("distribution", {"column": "price", "bins": 10}),
    ("categories", {"column": "property_type"}),
    ("funnel", {"column": "property_type"}),
    ("gauge", None),
    ("waterfall", {"initial": 100, "transforms": json.dumps(["Clean 1", "Clean 2"])})
]

# Note: scatter requires two numeric cols, let's skip for simple test unless we know cols

results = []
for route, params in routes_to_test:
    results.append(test_route(route, params))

print("\nFinal Result Summary:")
print(f"Passed: {sum(results)} / {len(results)}")

if all(results):
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
