import pandas as pd
import numpy as np
from app.services.data_processing_service import DataProcessingService

def diag():
    service = DataProcessingService()
    df = pd.DataFrame({
        'STREET': ['HURLEY', 'HURLEY', 'HURLEY', 'WENTWORTH'],
        'NUM_BEDROOMS': [3, 3, np.nan, 1],
        'date': pd.date_range('2023-01-01', periods=4),
        'target': ['A', 'B', 'A', 'B']
    })
    
    print("--- Testing auto_pilot ---")
    try:
        df_processed, transforms = service.auto_pilot(df)
        print("Auto-pilot success")
        print("Columns:", df_processed.columns.tolist())
        print("Shape:", df_processed.shape)
        
        print("\n--- Testing get_dataset_info ---")
        info = service.get_dataset_info(df_processed, "test_id")
        print("Get info success")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diag()
