import pandas as pd
from app.services.data_processing_service import DataProcessingService
import traceback

def diag():
    print("--- Loading property data.csv ---")
    try:
        # User's file from context
        df = pd.read_csv(r"c:\Users\NDOUR\Desktop\data\property data.csv")
        service = DataProcessingService()
        print("--- Running auto_pilot ---")
        df_processed, transforms = service.auto_pilot(df)
        print("--- Running get_dataset_info ---")
        info = service.get_dataset_info(df_processed, "test_id")
        
        import json
        print("--- Testing JSON serialization ---")
        json.dumps(info)
        print("Success! Columns:", df_processed.columns.tolist())
    except Exception as e:
        print(f"--- FAILED with {type(e).__name__} ---")
        traceback.print_exc()

if __name__ == "__main__":
    diag()
