import pandas as pd
import numpy as np
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(__file__))
from app.services.data_processing_service import DataProcessingService

def test_compliance():
    service = DataProcessingService()
    
    print("--- Starting Test 1 (Duplicates & High NaN) ---", flush=True)
    df_dup = pd.DataFrame({
        'A': [1, 2, 2, 3, 4], 
        'B': [pd.NA, pd.NA, pd.NA, 1, 2], # 60% NaN → > 40% threshold → dropped
        'C': [1, 2, 2, 3, 4]
    })
    df_res, trans = service.auto_pilot(df_dup)
    print(f"Test 1 Transformations:", flush=True)
    for t in trans:
        print(f"  → {t}", flush=True)
    assert len(df_res) == 4  # 1 duplicate removed
    assert 'B' not in df_res.columns  # B has > 40% NaN → dropped

    print("\n--- Starting Test 2 (Group-based & Target) ---", flush=True)
    df_group = pd.DataFrame({
        'group': ['A', 'A', 'A', 'B', 'B', 'B'],
        'val': [10, 11, 100, 20, 21, 22], # 100 is outlier in A
        'cat': ['Red', 'Blue', np.nan, 'Red', 'Blue', 'Red'],
        'target': ['Yes', 'No', 'Yes', 'No', 'Yes', 'No']
    })
    df_res, trans = service.auto_pilot(df_group)
    print(f"Test 2 Transformations: {trans}", flush=True)
    print(f"Test 2 Columns: {df_res.columns.tolist()}", flush=True)
    
    # Check outlier treatment in group A
    # The 100 should be capped/replaced
    # We need to find 'val' column in result
    if 'val' in df_res.columns:
        print(f"Val max: {df_res['val'].max()}", flush=True)
        assert df_res['val'].max() < 100
        
    # Check target encoding
    assert df_res['target'].dtype != object # Encoded to numeric
    assert df_res['target'].nunique() == 2

    print("\n--- Starting Test 3 (Time Series) ---", flush=True)
    df_time = pd.DataFrame({
        'date': pd.date_range('2023-01-01', periods=5),
        'val': [1, np.nan, 3, np.nan, 5]
    })
    df_res, trans = service.auto_pilot(df_time)
    print(f"Test 3 Transformations: {trans}", flush=True)
    assert not df_res['val'].isnull().any()

    print("\nCompliance Test Passed!", flush=True)

if __name__ == "__main__":
    try:
        test_compliance()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
