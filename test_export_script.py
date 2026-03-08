import os
import sys

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.routes.datasets import load_dataset
from app.services.data_processing_service import DataProcessingService

dataset_id = "666f0632-e97b-4d89-8b35-9613f2ba9c04"
service = DataProcessingService()

print(f"Loading dataset {dataset_id}...")
df = load_dataset(dataset_id)

if df is None:
    print("Dataset not found!")
    sys.exit(1)

print(f"Dataset loaded. Type: {type(df)}")

try:
    print("Exporting to CSV...")
    data, mime_type, ext = service.export_dataset(df, 'csv')
    print(f"Success! Size: {len(data)}")
except Exception as e:
    print(f"Error exporting to CSV: {e}")
    import traceback
    traceback.print_exc()

try:
    print("Exporting to XLSX...")
    data, mime_type, ext = service.export_dataset(df, 'xlsx')
    print(f"Success! Size: {len(data)}")
except Exception as e:
    print(f"Error exporting to XLSX: {e}")
    import traceback
    traceback.print_exc()
