import sys
import os
import traceback
import pandas as pd
import io

sys.path.insert(0, r'c:\Users\NDOUR\Desktop\data\data_analyst_back')

from app.services.data_processing_service import DataProcessingService

DATASETS_STORE_DIR = os.path.join(r'c:\Users\NDOUR\Desktop\data\data_analyst_back', 'temp_datasets')

def load_dataset(dataset_id):
    filepath = os.path.join(DATASETS_STORE_DIR, f"{dataset_id}.pkl")
    if os.path.exists(filepath):
        return pd.read_pickle(filepath)
    return None

# Redirect stdout to file to capture all debug prints
log_file = open(r'c:\Users\NDOUR\Desktop\data\data_analyst_back\debug_output.txt', 'w', encoding='utf-8')
sys.stdout = log_file
sys.stderr = log_file

try:
    print("Loading dataset...")
    df = load_dataset('113cabc9-d6f1-4ed9-80ab-e7bd6f45d380')
    if df is None:
        print("Dataset not found!")
    else:
        print(f"Dataset loaded: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        svc = DataProcessingService()
        print("Running autopilot...")
        df_out, transforms = svc.auto_pilot(df)
        print("Success! Transformations applied:")
        for t in transforms:
            print(f"  {t}")
except Exception as e:
    print(f"\nException caught: {e}")
    traceback.print_exc()
finally:
    log_file.close()
