"""Minimal compliance check - writes results to file."""
from app.services.data_processing_service import DataProcessingService
import pandas as pd
import numpy as np
import os

svc = DataProcessingService()
np.random.seed(42)
n = 100

df = pd.DataFrame({
    'client_id': range(n),
    'name': [f'Person_{i}' for i in range(n)],
    'age': np.random.randint(18, 80, n).astype(float),
    'salary': np.random.normal(50000, 15000, n),
    'date_joined': pd.date_range('2020-01-01', periods=n, freq='D'),
    'category': np.random.choice(['A', 'B', 'C'], n),
    'level': np.random.choice(['low', 'mid', 'high'], n),
    'constant_col': 'same_value',
    'target': np.random.choice([0, 1], n, p=[0.9, 0.1])
})
df.loc[5:10, 'age'] = np.nan
df.loc[15:20, 'salary'] = np.nan

r, t = svc.auto_pilot(df, 'classification', 'knn')

with open('compliance_results.txt', 'w', encoding='utf-8') as f:
    for i, x in enumerate(t, 1):
        f.write(f"[{i:2d}] {x}\n")
    f.write(f"\nShape: {r.shape}\n")
    f.write(f"Columns: {list(r.columns)}\n")
    
    checks = ['0.1', '0.4', 'A.1', 'A.2', 'B.1', 'C.1', 'C.2', 'C.3', 'D.', 'E.1', 'F.1', 'G.', 'H.4', '100%']
    f.write("\nCOMPLIANCE:\n")
    for k in checks:
        found = any(x.startswith(k) or k in x for x in t)
        f.write(f"  [{'PASS' if found else 'FAIL'}] {k}\n")
    
    f.write(f"\nPipeline file: {os.path.exists('saved_pipelines/preprocessor_pipeline.pkl')}\n")

print("Done. Results in compliance_results.txt")
