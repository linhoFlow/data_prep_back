"""Test auto_pilot on property data.csv with the fixed CompactOneHotEncoder."""
import sys, os, traceback
import pandas as pd

sys.path.insert(0, r'c:\Users\NDOUR\Desktop\data\data_analyst_back')
from app.services.data_processing_service import DataProcessingService

log_file = open(r'c:\Users\NDOUR\Desktop\data\data_analyst_back\debug_property.txt', 'w', encoding='utf-8')
sys.stdout = log_file
sys.stderr = log_file

try:
    df = pd.read_csv(r'c:\Users\NDOUR\Desktop\data\property data.csv')
    print(f"Loaded: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Dtypes:\n{df.dtypes}")
    print()
    svc = DataProcessingService()
    df_out, transforms = svc.auto_pilot(df, objective='classification', algorithm='knn')
    print(f"\nResult: {df_out.shape}")
    print(f"Result columns: {list(df_out.columns)}")
    print(f"\nTransformations:")
    for t in transforms:
        print(f"  {t}")
    print(f"\nFirst 5 rows:")
    print(df_out.head())
except Exception as e:
    print(f"\nException: {e}")
    traceback.print_exc()
finally:
    log_file.close()
