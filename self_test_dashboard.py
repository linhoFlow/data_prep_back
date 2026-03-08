import subprocess
import time
import urllib.request
import json
import os
import sys

def run_test():
    # Start the server
    print("Starting server...")
    server_process = subprocess.Popen([sys.executable, "run.py"], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE)
    
    time.sleep(8) # Wait for server to start
    
    if server_process.poll() is not None:
        print("Server failed to start!")
        out, err = server_process.communicate()
        print(f"STDOUT: {out.decode()}")
        print(f"STDERR: {err.decode()}")
        return

    print("Server started. Testing routes...")
    BASE_URL = "http://localhost:5000/api/datasets"
    DATASET_ID = "7096d4a7-c062-4bb5-a5a6-96c5cce5cb9a"
    
    routes = [
        ("types", None),
        ("quality", None),
        ("correlation", None),
        ("stats", {"column": "property_type"}),
        ("stats", {"column": "price"}),
        ("distribution", {"column": "price"}),
        ("categories", {"column": "property_type"}),
        ("funnel", {"column": "property_type"}),
        ("gauge", None),
        ("waterfall", {"initial": 100, "transforms": '["Clean"]'})
    ]
    
    all_passed = True
    for route, params in routes:
        param_str = ""
        if params:
            import urllib.parse
            param_str = "?" + urllib.parse.urlencode(params)
        
        url = f"{BASE_URL}/{DATASET_ID}/{route}{param_str}"
        try:
            with urllib.request.urlopen(url) as response:
                print(f"{route}: {response.getcode()}")
                if response.getcode() != 200:
                    all_passed = False
        except Exception as e:
            print(f"{route}: FAILED ({str(e)})")
            all_passed = False
            
    print("Terminating server...")
    server_process.terminate()
    server_process.wait()
    
    if all_passed:
        print("VÉRIFICATION RÉUSSIE : Tous les endpoints du dashboard sont opérationnels.")
    else:
        print("VÉRIFICATION ÉCHOUÉE : Certains endpoints ont renvoyé des erreurs.")

if __name__ == "__main__":
    run_test()
