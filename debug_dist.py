import pandas as pd
import polars as pl
import pickle
import os
from app.services.data_processing_service import DataProcessingService

temp_dir = 'temp_datasets'
latest = sorted(os.listdir(temp_dir))[-1]
filepath = f'{temp_dir}/{latest}'

with open(filepath, 'rb') as f:
    df = pickle.load(f)

print('DataFrame:')
print(f'Shape: {df.shape}')
print(f'Columns: {df.columns.tolist()}')
print(f'Dtypes: {df.dtypes.to_dict()}')
print()

# Convert to polars manually like the service does
print('Converting to Polars and testing...')
df_pl = pl.from_pandas(df)
col = 'ST_NAME'
print(f'Column {col} in Polars:')
print(f'  Polars dtype: {df_pl[col].dtype}')

try:
    series = df_pl[col].cast(pl.Float64, strict=False).drop_nulls()
    print(f'  After cast: {series.to_list()}')
    print(f'  Min: {series.min()}, Max: {series.max()}')
except Exception as e:
    print(f'  ERROR during cast: {e}')
    import traceback
    traceback.print_exc()

print()
print('=' * 60)

# Create service and test compute_distribution
service = DataProcessingService()

for col in ['ST_NAME', 'OWN_OCCUPIED']:
    print(f'Testing compute_distribution for {col}:')
    try:
        # Manually implement the logic to see where it fails
        df_pl = pl.from_pandas(df)
        if col not in df_pl.columns:
            print(f'  Column not found!')
            continue
            
        series = df_pl[col].cast(pl.Float64, strict=False).drop_nulls()
        print(f'  Series after cast: len={series.len()}, vals={series.to_list()[:3]}...')
        
        if series.is_empty():
            print(f'  Series is empty!')
            result = []
        else:
            min_v, max_v = float(series.min()), float(series.max())
            print(f'  Min={min_v}, Max={max_v}')
            bins = 5
            bin_width = (max_v - min_v) / bins
            print(f'  Bin width: {bin_width}')
            
            counts = []
            for i in range(bins):
                lo = min_v + i * bin_width
                hi = min_v + (i + 1) * bin_width
                if i == bins - 1:
                    c = series.filter((pl.element() >= lo) & (pl.element() <= hi)).len()
                else:
                    c = series.filter((pl.element() >= lo) & (pl.element() < hi)).len()
                counts.append({"range": f"{lo:.1f}", "count": int(c)})
            result = counts
        
        print(f'  Result: {result}')
    except Exception as e:
        print(f'  ERROR: {e}')
        import traceback
        traceback.print_exc()
    print()
