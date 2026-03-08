import os
import pandas as pd
import polars as pl
import io
from app.services.data_processing_service import DataProcessingService

service = DataProcessingService()

def test_upload_flow():
    # Sample data that might cause issues (e.g. columns with special chars or spaces)
    csv_content = """id,name,age,salary,dept
1,John,30,50000,HR
2,Jane,25,60000,IT
3,Bob,,45000,Sales
4,Alice,35,,HR
5,Charlie,40,70000,
"""
    filename = "test.csv"
    file_bytes = csv_content.encode('utf-8')
    
    print(">>> Testing parse_file")
    df, err = service.parse_file(file_bytes, filename)
    if err:
        print(f"Parse error: {err}")
        return
    
    print(f"Parsed DF shape: {df.shape}")
    print(f"Columns: {df.columns}")
    
    print(">>> Testing get_dataset_info")
    try:
        info = service.get_dataset_info(df, "test_id")
        print("get_dataset_info success!")
    except Exception as e:
        print(f"get_dataset_info FAILED: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_upload_flow()
