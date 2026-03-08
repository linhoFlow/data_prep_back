# -*- coding: utf-8 -*-
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from app.services.data_processing_service import DataProcessingService

service = DataProcessingService()
PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")

# =========================
# TEST 1: Meme nombre de colonnes en sortie
# =========================
print("\n=== TEST 1: Nombre de colonnes preserve ===")
df = pd.DataFrame({
    'age': [25, 30, 35, 40, 45],
    'salaire': [3000, 4000, 5000, 6000, 7000],
    'ville': ['Paris', 'Lyon', 'Paris', 'Lyon', 'Paris'],
    'niveau': ['A', 'B', 'C', 'A', 'B'],
})
df_res, trans = service.auto_pilot(df.copy())
check("Colonnes entree == sortie", df_res.shape[1] == df.shape[1])
check("Aucun NaN restant", df_res.isnull().sum().sum() == 0)
print(f"  Colonnes: {df.shape[1]} -> {df_res.shape[1]}")

# =========================
# TEST 2: Z-score remplacement
# =========================
print("\n=== TEST 2: Z-score - remplacement correct ===")
from app.services.data_processing_service import OutlierHandler

# Distribution normale (skew < 0.5) -> remplacement par moyenne
np.random.seed(42)
normal_data = pd.DataFrame({'val': np.random.normal(50, 5, 200)})
skew_normal = abs(normal_data['val'].skew())
print(f"  Skew normale: {skew_normal:.3f}")
handler = OutlierHandler()
handler.fit(normal_data)
p = handler.params_['val']['stats']
check("Dist normale -> methode zscore", p['method'] == 'zscore')
check("Dist normale -> is_normal=True", p.get('is_normal') == True)
check("Dist normale -> replacement=mean", abs(p['replacement'] - p['mean']) < 0.01)

# Distribution quasi-normale (0.2 <= skew < 0.5) -> remplacement par mediane
np.random.seed(123)
quasi_data = pd.DataFrame({'val': np.random.lognormal(3.9, 0.1, 200)})
skew_val = abs(quasi_data['val'].skew())
print(f"  Skew quasi-normale: {skew_val:.3f}")
handler2 = OutlierHandler()
handler2.fit(quasi_data)
p2 = handler2.params_['val']['stats']
if 0.2 <= skew_val < 0.5:
    check("Dist quasi-normale -> methode zscore", p2['method'] == 'zscore')
    check("Dist quasi-normale -> is_normal=False", p2.get('is_normal') == False)
    check("Dist quasi-normale -> replacement=median", abs(p2['replacement'] - p2['median']) < 0.01)
else:
    print(f"  SKIP: skew={skew_val:.2f} (expected [0.2, 0.5))")

# =========================
# TEST 3: KNNImputer seuil NaN < 30%
# =========================
print("\n=== TEST 3: KNNImputer seuil NaN < 30% ===")
from app.services.data_processing_service import MissingValueHandler

# 20% NaN + correlation -> should choose KNN
df_knn = pd.DataFrame({
    'a': [1, 2, np.nan, 4, 5, 6, 7, np.nan, 9, 10], 
    'b': [1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1], # Highly correlated
})
handler_knn = MissingValueHandler(missing_analysis={'a': {'type': 'MAR'}})
handler_knn.fit(df_knn)
strat_a = handler_knn.statistics_[0].get('strategy')
check("20% NaN + correlation -> KNN choisie", strat_a == 'knn')

# 40% NaN -> ne devrait PAS choisir KNN (> 30%)
df_high = pd.DataFrame({
    'a': [1, np.nan, np.nan, np.nan, 5, 6, np.nan, 8, 9, 10],
    'b': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
})
handler_high = MissingValueHandler()
handler_high.fit(df_high)
strat_high = handler_high.statistics_[0].get('strategy')
check("40% NaN -> KNN PAS choisie (iterative)", strat_high != 'knn')

# =========================
# TEST 4: Seuil suppression colonnes (DSABLED in autopilot to keep same count)
# =========================
print("\n=== TEST 4: Conservation des colonnes ===")
df_nan = pd.DataFrame({
    'A': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    'B': [1, 2, np.nan, np.nan, np.nan, np.nan, np.nan, 8, 9, 10], # 50% NaN
    'C': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
})
df_res4, trans4 = service.auto_pilot(df_nan.copy())
check("Colonne B (50% NaN) conservee (meme nombre de colonnes)", 'B' in df_res4.columns)
check("Colonnes count correct", len(df_res4.columns) == 3)

# =========================
# TEST 5: Suppression lignes
# =========================
print("\n=== TEST 5: Preference suppression lignes ===")
df_rows = pd.DataFrame({
    'A': [1,    2,    np.nan, 4, 5],
    'B': [10,   20,   np.nan, 40, 50],
    'C': ['x',  'y',  np.nan, 'w', 'v'],
})
# Ligne 2 a 100% NaN
df_res5, trans5 = service.auto_pilot(df_rows.copy())
has_row_deletion = any("lignes" in t for t in trans5)
check("Lignes avec NaN eleve supprimees", has_row_deletion)

# =========================
# TEST 6: Logs detailles
# =========================
print("\n=== TEST 6: Logs detailles ===")
df_log = pd.DataFrame({
    'age': [25, 30, 35, np.nan, 45, 50, 55, 60],
    'salaire': [3000, 4000, np.nan, 6000, 7000, 8000, 9000, 10000],
    'ville': ['Paris', 'Lyon', np.nan, 'Lyon', 'Paris', 'Lyon', 'Paris', 'Lyon'],
})
df_log_res, trans_log = service.auto_pilot(df_log.copy())
has_exigence = any("Exigence" in t for t in trans_log)
check("Logs contiennent 'Exigence'", has_exigence)
has_scaling = any("Scaling" in t for t in trans_log)
check("Logs contiennent 'Scaling'", has_scaling)

# =========================
# RESUME
# =========================
print(f"\n{'='*50}")
print(f"  RESULTAT: {PASS} passes, {FAIL} echoues")
print(f"{'='*50}")
sys.exit(1 if FAIL > 0 else 0)
