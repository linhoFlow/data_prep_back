import pandas as pd
import numpy as np
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer, KNNImputer

print("Testing simple imputation...", flush=True)
df = pd.DataFrame({'A': [1, 2, np.nan, 4], 'B': [1, np.nan, 3, 4]})
imputer = IterativeImputer(max_iter=5)
res = imputer.fit_transform(df)
print("IterativeImputer OK:", res.shape, flush=True)

imputer_knn = KNNImputer()
res_knn = imputer_knn.fit_transform(df)
print("KNNImputer OK:", res_knn.shape, flush=True)
