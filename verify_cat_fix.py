import pandas as pd
import polars as pl
import io
import os
import traceback
from app.services.data_processing_service import DataProcessingService

service = DataProcessingService()

def test_categorical_fix():
    file_path = r"c:\Users\NDOUR\Desktop\data\property data.csv"
    if not os.path.exists(file_path):
        print("File not found")
        return

    with open(file_path, "rb") as f:
        content = f.read()
    
    df, err = service.parse_file(content, "property data.csv")
    if err:
        print(f"Parse error: {err}")
        return

    print(">>> Running auto_pilot (objective=classification, algorithm=rf)")
    try:
        # 'rf' is in TREE_ALGOS, so scaling/encoding is disabled
        df_clean, transforms = service.auto_pilot(df, objective='classification', algorithm='rf')
        
        print(">>> Transformations applied:")
        for t in transforms:
            print(f" - {t}")
        
        if any("OWN_OCCUPIED" in t for t in transforms):
            print("SUCCESS: OWN_OCCUPIED inconsistency found and transformed!")
        else:
            print("FAILURE: OWN_OCCUPIED inconsistency NOT transformed.")

        # Check the actual values in OWN_OCCUPIED
        if 'OWN_OCCUPIED' in df_clean.columns:
            values = df_clean['OWN_OCCUPIED'].unique()
            print(f"Unique values in OWN_OCCUPIED: {values}")
            if '12' in values or 12 in values:
                print("FAILURE: '12' still present in OWN_OCCUPIED.")
            else:
                print("SUCCESS: '12' removed from OWN_OCCUPIED.")
        else:
            print("OWN_OCCUPIED column missing in result (maybe dropped?)")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_categorical_fix()
