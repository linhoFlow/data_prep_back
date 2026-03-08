import sys
import os
import pandas as pd
import polars as pl
import json
import traceback

# Add backend to path
sys.path.append(r'c:\Users\NDOUR\Desktop\data\data_analyst_back')

from app.services.data_processing_service import DataProcessingService

def diag():
    log_file = r'c:\Users\NDOUR\Desktop\data\data_analyst_back\diag_output.txt'
    with open(log_file, 'w', encoding='utf-8') as f:
        service = DataProcessingService()
        dataset_dir = r'c:\Users\NDOUR\Desktop\data\data_analyst_back\temp_datasets'
        
        # Test a few recent datasets
        files = [f for f in os.listdir(dataset_dir) if f.endswith('.pkl')]
        # Sort by modification time (most recent first)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(dataset_dir, x)), reverse=True)
        
        for file in files[:10]: # Check first 10
            path = os.path.join(dataset_dir, file)
            dataset_id = file.replace('.pkl', '')
            f.write(f"\n--- Testing Dataset: {dataset_id} ---\n")
            try:
                df = pd.read_pickle(path)
                f.write(f"Shape: {df.shape}\n")
                
                f.write("Testing get_dataset_info...\n")
                service.get_dataset_info(df, dataset_id)
                
                f.write("Testing compute_quality_stats...\n")
                service.compute_quality_stats(df)
                
                f.write("Testing compute_gauge_data...\n")
                service.compute_gauge_data(df)
                
                f.write("Testing compute_correlation_matrix...\n")
                service.compute_correlation_matrix(df)
                
                f.write("Testing compute_type_distribution...\n")
                service.compute_type_distribution(df)
                
                f.write(f"✅ SUCCESS for {dataset_id}\n")
            except Exception as e:
                f.write(f"❌ FAILED for {dataset_id}: {str(e)}\n")
                f.write(traceback.format_exc())
                f.write("\n")

if __name__ == "__main__":
    diag()
