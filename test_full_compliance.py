"""Test full preprocessing compliance (Sections 0-H)."""
from app.services.data_processing_service import DataProcessingService
import pandas as pd
import numpy as np
import os

svc = DataProcessingService()
np.random.seed(42)
n = 100

# Build test dataset with all edge cases
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
df.loc[25:30, 'category'] = np.nan

print("=" * 70)
print(f"INPUT: Shape={df.shape}, Columns={list(df.columns)}")
print("=" * 70)

result_df, transformations = svc.auto_pilot(
    df, objective='classification', algorithm='knn'
)

print("\n" + "=" * 70)
print(f"TRANSFORMATIONS ({len(transformations)} steps):")
print("=" * 70)
for i, t in enumerate(transformations, 1):
    print(f"  [{i:2d}] {t}")

print(f"\nOUTPUT: Shape={result_df.shape}, Columns={list(result_df.columns)}")

sections = {
    '0.1': False, '0.4': False, 'A.1': False,
    'A.2': False, 'B.1': False, 'C.1': False, 'C.2': False,
    'C.3': False, 'D.1': False, 'E.1': False, 'F.1': False,
    'G.': False, 'H.4': False, 'Pipeline complet': False
}

for t in transformations:
    for key in sections:
        if t.startswith(key) or key in t:
            sections[key] = True

print("\nCOMPLIANCE:")
for key, val in sections.items():
    print(f"  [{'PASS' if val else 'FAIL'}] {key}")

if os.path.exists(os.path.join('saved_pipelines', 'preprocessor_pipeline.pkl')):
    print("  [PASS] Pipeline file exists")
