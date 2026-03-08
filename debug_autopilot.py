import pandas as pd
from app.services.data_processing_service import DataProcessingService
import traceback
import sys

def debug_process():
    print("--- Starting Debug ---")
    try:
        csv_path = r'C:\Users\NDOUR\Desktop\data\property data.csv'
        print(f"Loading {csv_path}...")
        df = pd.read_csv(csv_path)
        print(f"Loaded DataFrame: {df.shape}")
        
        svc = DataProcessingService()
        print("Parsing...")
        df_pl, err = svc.parse_file(open(csv_path, 'rb').read(), 'property data.csv')
        if err:
            print(f"Parse error: {err}")
            return
            
        print(f"Parsed into Polars DataFrame: {df_pl.height}x{df_pl.width}")
        
        print("Running AutoPilot...")
        res_df, transforms = svc.auto_pilot(
            df_pl,
            objective='classification',
            algorithm=['auto'],
            nlp_mode='',
            is_guest=False
        )
        print("AutoPilot Success!")
        print(f"Final shape: {res_df.height}x{res_df.width}")
        print("Transformations:", transforms)
        
    except Exception as e:
        print("\n--- CRITICAL ERROR ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    debug_process()
