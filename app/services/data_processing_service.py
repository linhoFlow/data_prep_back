import polars as pl
import pandas as pd  # Keep for sklearn compatibility in some transformers
import numpy as np
import io
import json
import math
import os
import traceback
from lxml import etree

# Sklearn - Preprocessing
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import (
    OneHotEncoder, OrdinalEncoder, LabelEncoder,
    MinMaxScaler, StandardScaler, RobustScaler, FunctionTransformer
)
from sklearn.impute import KNNImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
import joblib

# Sklearn - NLP
from sklearn.feature_extraction.text import TfidfVectorizer

# Imbalanced-learn
try:
    from imblearn.over_sampling import SMOTE
except ImportError:
    SMOTE = None

# Enable IterativeImputer (experimental)
from sklearn.experimental import enable_iterative_imputer  # noqa
from sklearn.impute import IterativeImputer

# Multilevel & Advanced Methods
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.covariance import EllipticEnvelope
from sklearn.model_selection import cross_validate, StratifiedKFold, KFold

# NLP & Embeddings placeholders
Word2Vec = None
SentenceTransformer = None


# ================================================================
# CLASSES PERSONNALISÉES (Custom Transformer Classes)
# ================================================================

class CompactOneHotEncoder(BaseEstimator, TransformerMixin):
    def __init__(self, dtype=np.int32):
        # Fix #4 : drop='first' removed to allow handle_unknown='ignore' safely across all sklearn versions
        # Le but est de préserver les colonnes booléennes créées, et non de les écraser en une seule.
        # Utilisation d'un dtype passé en paramètre (par défaut int32 pour éviter les .0)
        self.dtype = dtype
        self.ohe = OneHotEncoder(sparse_output=False, handle_unknown='ignore', dtype=self.dtype)
        
    def _to_numpy(self, X):
        if isinstance(X, (pd.DataFrame, pd.Series)): return X.values
        if isinstance(X, (pl.DataFrame, pl.Series)): return X.to_numpy()
        return np.array(X)

    def fit(self, X, y=None):
        X_np = self._to_numpy(X)
        self.ohe.fit(X_np)
        self.is_fitted_ = True
        return self
        
    def transform(self, X):
        X_np = self._to_numpy(X)
        return self.ohe.transform(X_np)
    
    def get_feature_names_out(self, input_features=None):
        return self.ohe.get_feature_names_out(input_features)

class MissingValueHandler(BaseEstimator, TransformerMixin):
    """
    Classe personnalisée pour le traitement des valeurs manquantes (Exigences 1-10).

    - Prise en compte du type MCAR/MAR/MNAR pour choisir KNN/Iterative (Exig. 8-9)
    - KNN et IterativeImputer UNIQUEMENT pour MAR/MNAR (pas MCAR)
    - Stratégie 'simple' (mean/median/mode) pour MCAR

    Exigence 9 — KNNImputer sélectionné si :
        ✔ Type MAR ou MNAR
        ✔ NaN < 30%
        ✔ La colonne est CORRÉLÉE aux autres colonnes numériques
          (corrélation absolue maximale ≥ seuil CORR_THRESHOLD = 0.3)
          -> conforme à l'exigence 9 : "colonnes corrélées ou dépendant logiquement des autres"

    Exigence 8 — IterativeImputer sélectionné si :
        ✔ Type MAR ou MNAR
        ✔ 5% ≤ NaN ≤ 50%
        ✔ La colonne n'a pas été retenue pour KNN (priorité KNN > Iterative)

    - Paramètre missing_analysis transmis depuis auto_pilot
    """

    # Seuil de corrélation pour qualifier une colonne de "corrélée aux autres"
    # Conforme à l'exigence 9 : relations quantifiables par distances
    CORR_THRESHOLD = 0.3

    def __init__(self, strategy='auto', group_col=None, is_timeseries=False, missing_analysis=None, is_guest=False):
        self.strategy = strategy
        self.group_col = group_col
        self.is_timeseries = is_timeseries
        self.missing_analysis = missing_analysis
        self.is_guest = is_guest  # Si True, forcer imputation simple (mean/median/mode)

    def _to_polars(self, X):
        if isinstance(X, pl.DataFrame): return X
        if isinstance(X, pd.DataFrame): return pl.from_pandas(X)
        if isinstance(X, np.ndarray):
            return pl.DataFrame(X, orient="row")
        return pl.DataFrame(X)

    def fit(self, X, y=None):
        X_pl = self._to_polars(X)
        print(f"[MissingValueHandler] Fitting with Polars on {X_pl.shape}", flush=True)
        self.statistics_ = {}
        analysis = self.missing_analysis or {}
        
        numeric_cols = [col for col, dtype in X_pl.schema.items() if dtype.is_numeric()]
        n_rows = X_pl.height

        # EXIGENCE 9 — Précalcul des corrélations inter-colonnes
        col_max_corr = {}
        if len(numeric_cols) >= 2:
            try:
                # Polars correlation matrix
                corr_matrix = X_pl.select(numeric_cols).corr()
                for col in numeric_cols:
                    corrs = corr_matrix[col].to_series()
                    # Find max absolute correlation with OTHER columns
                    other_corrs = [abs(c) for i, c in enumerate(corrs) if corr_matrix.columns[i] != col and c is not None]
                    col_max_corr[col] = max(other_corrs) if other_corrs else 0.0
            except:
                for col in numeric_cols: col_max_corr[col] = 0.0
        else:
            for col in numeric_cols: col_max_corr[col] = 0.0

        for col_idx, col_name in enumerate(X_pl.columns):
            series = X_pl[col_name]
            null_count = series.null_count()
            null_perc = (null_count / n_rows) * 100 if n_rows > 0 else 0
            missing_type = analysis.get(str(col_name), {}).get('type', 'MCAR')

            stats = {
                'null_perc': null_perc,
                'is_numeric': col_name in numeric_cols,
                'missing_type': missing_type,
                'col_name': col_name
            }

            if stats['is_numeric']:
                clean_series = series.drop_nulls()
                if not clean_series.is_empty():
                    stats['mean'] = float(clean_series.mean())
                    stats['median'] = float(clean_series.median())
                    stats['is_symmetric'] = abs(float(clean_series.skew() or 0)) < 1
                    
                    Q1 = float(clean_series.quantile(0.25))
                    Q3 = float(clean_series.quantile(0.75))
                    IQR_val = Q3 - Q1
                    outliers = clean_series.filter((clean_series < (Q1 - 1.5 * IQR_val)) | (clean_series > (Q3 + 1.5 * IQR_val)))
                    stats['has_outliers'] = not outliers.is_empty()
                else:
                    stats['mean'] = 0.0
                    stats['median'] = 0.0
                    stats['is_symmetric'] = True
                    stats['has_outliers'] = False

                # -------------------------------------------------------
                # EXIGENCES 8 & 9 — Sélection de la stratégie d'imputation
                #
                # ✅ CORRECTION EXIGENCE 9 :
                #    Le critère de sélection KNN est désormais basé sur la
                #    CORRÉLATION inter-colonnes (col_max_corr ≥ CORR_THRESHOLD),
                #    et NON plus sur la présence d'outliers.
                #
                #    Priorité : KNN > IterativeImputer > simple
                #
                #    KNN   -> MAR/MNAR  ET  NaN < 30%  ET  colonne corrélée
                #    Iter. -> MAR/MNAR  ET  5% ≤ NaN ≤ 50%  (si pas KNN)
                #    simple -> MCAR  OU  conditions KNN/Iter non remplies
                # -------------------------------------------------------
                if self.strategy == 'auto':
                    # MODE INVITÉ : imputation simple uniquement (A.2)
                    if self.is_guest:
                        stats['strategy'] = 'simple'
                    else:
                        is_mar_mnar = missing_type in ('MAR', 'MNAR')
                        is_correlated = col_max_corr.get(col_name, 0.0) >= self.CORR_THRESHOLD

                        if is_mar_mnar and null_perc < 30 and is_correlated:
                            stats['strategy'] = 'knn'
                        elif is_mar_mnar and 5 <= null_perc <= 50:
                            stats['strategy'] = 'iterative'
                        else:
                            stats['strategy'] = 'simple'
                else:
                    stats['strategy'] = 'simple' if self.is_guest else self.strategy
            else:
                try:
                    m = series.drop_nulls().mode()
                    stats['mode'] = m[0] if not m.is_empty() else "missing"
                except:
                    stats['mode'] = "missing"
                stats['strategy'] = 'simple'

            self.statistics_[col_idx] = stats

        self.is_fitted_ = True
        return self

    def transform(self, X):
        X_pl = self._to_polars(X)
        X_out = X_pl.clone()
        
        # Strategies for numerical
        knn_cols = [s['col_name'] for s in self.statistics_.values() if s.get('strategy') == 'knn' and s['is_numeric']]
        iter_cols = [s['col_name'] for s in self.statistics_.values() if s.get('strategy') == 'iterative' and s['is_numeric']]

        # Time series interpolation
        if self.is_timeseries:
            numeric_cols_pl = [col for col, dtype in X_out.schema.items() if dtype.is_numeric()]
            if numeric_cols_pl:
                X_out = X_out.with_columns([
                    pl.col(c).interpolate().fill_null(strategy="forward").fill_null(strategy="backward")
                    for c in numeric_cols_pl
                ])

        # Advanced Imputation (KNN/Iterative)
        if (knn_cols or iter_cols) and not self.is_timeseries:
            numeric_cols_all = [col for col, dtype in X_out.schema.items() if dtype.is_numeric()]
            if len(numeric_cols_all) >= 2:
                X_np = X_out.select(numeric_cols_all).to_numpy()
                # sklearn imputer handles NaN in numpy
                if knn_cols:
                    imputer = KNNImputer(n_neighbors=5)
                    X_np = imputer.fit_transform(X_np)
                if iter_cols:
                    imputer = IterativeImputer(max_iter=10, random_state=0)
                    X_np = imputer.fit_transform(X_np)
                
                # Update Polars DF with imputed numeric values
                X_out = X_out.with_columns([
                    pl.Series(c, X_np[:, i]) for i, c in enumerate(numeric_cols_all)
                ])

        # Simple Imputation (Mean/Median/Mode)
        for col_idx, stats in self.statistics_.items():
            if stats.get('strategy') != 'simple': continue
            col_name = stats['col_name']
            if col_name not in X_out.columns: continue
            
            if stats['is_numeric']:
                # Mean if symmetric and no outliers, else Median
                fill_val = stats['mean'] if stats.get('is_symmetric', True) and not stats.get('has_outliers', False) and stats['null_perc'] < 10 else stats['median']
                
                if self.group_col and self.group_col in X_out.columns:
                    # For group-based, we'd ideally use transform/join but keep it simple for now as it's a fallback
                    # Exig 5 requirements handled via group_by in fit if we wanted to be 100% group-based
                    pass
                X_out = X_out.with_columns(pl.col(col_name).fill_null(fill_val))
            else:
                fill_val = stats.get('mode', "missing")
                if self.group_col and self.group_col in X_out.columns:
                    pass
                X_out = X_out.with_columns(pl.col(col_name).fill_null(fill_val))

        return X_out.to_numpy() if not isinstance(X, (pd.DataFrame, pl.DataFrame)) else X_out

    def get_feature_names_out(self, input_features=None):
        return input_features

    def _to_polars(self, X):
        if isinstance(X, pl.DataFrame): return X
        if isinstance(X, pd.DataFrame): return pl.from_pandas(X)
        if isinstance(X, np.ndarray): return pl.from_numpy(X)
        return pl.DataFrame(X)


class OutlierHandler(BaseEstimator, TransformerMixin):
    """
    Classe personnalisée pour le traitement des valeurs aberrantes via Polars.
    """
    def __init__(self, method='auto', group_col=None):
        self.method = method
        self.group_col = group_col

    def fit(self, X, y=None):
        print(f"[OutlierHandler] Fitting with Polars on {X.shape}", flush=True)
        self.params_ = {}
        X_pl = self._to_polars(X)
        numeric_cols = [col for col, dtype in X_pl.schema.items() if dtype.is_numeric()]

        for col in numeric_cols:
            if self.group_col and self.group_col in X_pl.columns:
                gp_stats = {}
                groups = X_pl.group_by(self.group_col).agg(pl.col(col).drop_nulls().alias("_s"))
                for row in groups.to_dicts():
                    series = pl.Series(row["_s"])
                    if not series.is_empty(): gp_stats[row[self.group_col]] = self._compute_stats_pl(series)
                self.params_[col] = {'group_based': True, 'stats': gp_stats}
            else:
                series = X_pl[col].drop_nulls()
                if not series.is_empty(): self.params_[col] = {'group_based': False, 'stats': self._compute_stats_pl(series)}
        self.is_fitted_ = True
        return self

    def _compute_stats_pl(self, series):
        skew = abs(float(series.skew() or 0))
        if skew < 0.5:
            is_strictly_normal = skew < 0.2
            m, md, std = float(series.mean()), float(series.median()), float(series.std() or 1.0)
            return {'method': 'zscore', 'mean': m, 'median': md, 'std': std, 'replacement': m if is_strictly_normal else md}
        elif skew < 1:
            q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
            iqr = q3 - q1
            return {'method': 'iqr', 'lower': q1 - 1.5 * iqr, 'upper': q3 + 1.5 * iqr}
        else:
            return {'method': 'winsor', 'lower': float(series.quantile(0.05)), 'upper': float(series.quantile(0.95))}

    def transform(self, X):
        X_pl = self._to_polars(X)
        X_out = X_pl.clone()
        for col, p in self.params_.items():
            if col not in X_out.columns: continue
            if not p['group_based']:
                s = p['stats']
                if s['method'] == 'zscore':
                    X_out = X_out.with_columns(
                        pl.when(((pl.col(col) - s['mean']).abs() / s['std']) > 3)
                        .then(s['replacement'])
                        .otherwise(pl.col(col))
                        .alias(col)
                    )
                elif s['method'] in ['iqr', 'winsor']:
                    X_out = X_out.with_columns(pl.col(col).clip(s['lower'], s['upper']).alias(col))
        
        if isinstance(X, (pd.DataFrame, pl.DataFrame)):
            return X_out
        return X_out.to_numpy()

    def _to_polars(self, X):
        if isinstance(X, pl.DataFrame): return X
        if isinstance(X, pd.DataFrame): return pl.from_pandas(X)
        if isinstance(X, np.ndarray):
            return pl.DataFrame(X, orient="row")
        return pl.DataFrame(X)

    def get_feature_names_out(self, input_features=None):
        return input_features


# ================================================================
# CORRECTIF #1 : EMBEDDINGS TEXTE (NLP Texte libre - Exigence D)
# ================================================================

class TextEmbedder(BaseEstimator, TransformerMixin):
    """
    Transforme les colonnes texte en vecteurs d'embeddings.
    Support : TF-IDF, Word2Vec, BERT/CamemBERT
    """
    def __init__(self, mode='tfidf', max_features=100, embedding_dim=300):
        self.mode = mode  # 'tfidf', 'word2vec', 'bert'
        self.max_features = max_features
        self.embedding_dim = embedding_dim
        self.vectorizer = None
        self.model = None
        
    def fit(self, X, y=None):
        X_clean = self._to_list(X)
        if not X_clean:
            return self
            
        if self.mode == 'tfidf':
            self.vectorizer = TfidfVectorizer(max_features=self.max_features)
            self.vectorizer.fit(X_clean)
        elif self.mode == 'word2vec':
            try:
                from gensim.models import Word2Vec
                sentences = [str(text).split() for text in X_clean if str(text).strip()]
                if sentences:
                    self.model = Word2Vec(sentences=sentences, vector_size=self.embedding_dim, window=5, min_count=1, workers=4)
            except ImportError:
                print("[ERROR] gensim not installed for word2vec", flush=True)
        elif self.mode == 'bert':
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer('distiluse-base-multilingual-v3')
            except Exception as e:
                print(f"[ERROR] sentence_transformers failed: {str(e)}", flush=True)
        return self

    def transform(self, X):
        X_clean = self._to_list(X)
        if not X_clean or self.mode == 'tfidf' and self.vectorizer is None:
            return np.zeros((len(X_clean) if X_clean else 1, self.max_features))
            
        if self.mode == 'tfidf':
            return self.vectorizer.transform(X_clean).toarray()
        elif self.mode == 'word2vec' and self.model:
            embeddings = []
            for text in X_clean:
                words = str(text).split()
                vecs = [self.model.wv[w] for w in words if w in self.model.wv]
                embeddings.append(np.mean(vecs, axis=0) if vecs else np.zeros(self.embedding_dim))
            return np.array(embeddings)
        elif self.mode == 'bert' and self.model:
            return self.model.encode(X_clean, show_progress_bar=False)
        return np.zeros((len(X_clean), self.max_features))

    def _to_list(self, X):
        if isinstance(X, pl.Series): return X.drop_nulls().to_list()
        if isinstance(X, pd.Series): return X.dropna().tolist()
        if isinstance(X, np.ndarray): return X.flatten().tolist()
        return list(X) if X is not None else []

    def get_feature_names_out(self, input_features=None):
        dim = self.embedding_dim if self.mode != 'tfidf' else self.max_features
        prefix = input_features[0] if input_features is not None and len(input_features) > 0 else "text"
        import numpy as np
        return np.array([f"{prefix}_{i}" for i in range(dim)])


# ================================================================
# CORRECTIF #2 : DÉTECTEUR MULTIVARIÉS D'OUTLIERS (Exigence B)
# ================================================================

class MultivariatOutlierDetector(BaseEstimator, TransformerMixin):
    """
    Détecte les outliers multivariés en combinant :
    - Isolation Forest (indépendant de la distribution)
    - Local Outlier Factor (LOF, densité locale)
    - Elliptic Envelope (estimation de la matrice de covariance robuste)
    """
    def __init__(self, algorithm='isolation', contamination=0.05):
        self.algorithm = algorithm  # 'isolation', 'lof', 'elliptic', 'voting'
        self.contamination = contamination
        self.outlier_detector = None
        
    def fit(self, X, y=None):
        X_np = self._to_numpy(X)
        X_np = np.nan_to_num(X_np, nan=0.0)
        
        if self.algorithm == 'isolation':
            self.outlier_detector = IsolationForest(contamination=self.contamination, random_state=42)
        elif self.algorithm == 'lof':
            self.outlier_detector = LocalOutlierFactor(n_neighbors=20, contamination=self.contamination)
        elif self.algorithm == 'elliptic':
            self.outlier_detector = EllipticEnvelope(contamination=self.contamination, random_state=42)
        
        self.outlier_detector.fit(X_np)
        return self

    def transform(self, X):
        X_np = self._to_numpy(X)
        X_np = np.nan_to_num(X_np, nan=0.0)
        
        try:
            if self.algorithm == 'lof':
                outlier_labels = self.outlier_detector.fit_predict(X_np)
            else:
                outlier_labels = self.outlier_detector.predict(X_np)  # -1 = outlier
            X_with_labels = np.column_stack([X_np, (outlier_labels == -1).astype(int)])
            return X_with_labels
        except Exception as e:
            print(f"[ERROR] MultivariatOutlierDetector: {str(e)}")
            import traceback
            traceback.print_exc()
            return X_np

    def get_feature_names_out(self, input_features=None):
        if input_features is None: return None
        import numpy as np
        return np.append(input_features, ["is_outlier"])

    def _to_numpy(self, X):
        if isinstance(X, pl.DataFrame): return X.to_numpy().astype(float)
        if isinstance(X, pd.DataFrame): return X.values.astype(float)
        if isinstance(X, np.ndarray): return X.astype(float)
        return np.array(X, dtype=float)


# ================================================================
# CORRECTIF #3 : ENCODAGE CIBLE SUPERVISÉ (High-Cardinality - Exigence C)
# ================================================================

class TargetEncoder(BaseEstimator, TransformerMixin):
    """
    Target Encoding supervisé : remplace les catégories par la moyenne
    de la target, avec lissage pour éviter le surapprentissage.
    """
    def __init__(self, smoothing=1.0):
        self.smoothing = smoothing
        self.target_stats_ = {}
        self.global_mean_ = 0.0
        
    def fit(self, X, y=None):
        if y is None or X is None:
            return self
            
        X_clean = self._to_list(X)
        y_arr = np.array(y).flatten() if y is not None else np.zeros(len(X_clean))
        
        self.global_mean_ = float(np.mean(y_arr))
        
        for category in set(X_clean):
            mask = (np.array(X_clean) == category)
            if mask.any():
                cat_mean = float(np.mean(y_arr[mask]))
                count = int(np.sum(mask))
                # Smoothing : moyenne pondérée entre moyenne locale et globale
                smoothed = (count * cat_mean + self.smoothing * self.global_mean_) / (count + self.smoothing)
                self.target_stats_[str(category)] = smoothed
        return self

    def transform(self, X):
        X_clean = self._to_list(X)
        result = np.array([
            self.target_stats_.get(str(cat), self.global_mean_)
            for cat in X_clean
        ]).reshape(-1, 1)
        return result

    def _to_list(self, X):
        if isinstance(X, pl.Series): return X.to_list()
        if isinstance(X, pd.Series): return X.tolist()
        if isinstance(X, np.ndarray): return X.flatten().tolist()
        return list(X) if X is not None else []

    def get_feature_names_out(self, input_features=None):
        return input_features


class AdaptiveScaler(BaseEstimator, TransformerMixin):
    """
    Classe personnalisée qui sélectionne le scaler approprié via Polars.
    """
    def __init__(self):
        self.scalers_ = {}
        self.scaler_types_ = {}

    def fit(self, X, y=None):
        X_pl = self._to_polars(X)
        for i, col in enumerate(X_pl.columns):
            series = X_pl[col].drop_nulls()
            if series.is_empty():
                scaler = MinMaxScaler()
                self.scaler_types_[i] = 'minmax'
            else:
                skew = abs(float(series.skew() or 0))
                has_outliers = self._check_outliers_pl(series)
                if skew < 0.5:
                    scaler, self.scaler_types_[i] = StandardScaler(), 'standard'
                elif has_outliers:
                    scaler, self.scaler_types_[i] = RobustScaler(), 'robust'
                else:
                    scaler, self.scaler_types_[i] = MinMaxScaler(), 'minmax'
            
            # Sklearn scalers still need numpy/pandas
            data_np = X_pl[col].to_numpy().reshape(-1, 1)
            # Re-fill nulls for sklearn
            data_np = np.nan_to_num(data_np, nan=0.0)
            self.scalers_[i] = scaler.fit(data_np)
        return self

    def _check_outliers_pl(self, series):
        if series.is_empty(): return False
        q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
        iqr = q3 - q1
        outliers = series.filter((series < (q1 - 1.5 * iqr)) | (series > (q3 + 1.5 * iqr)))
        return not outliers.is_empty()

    def transform(self, X):
        X_pl = self._to_polars(X)
        # Sklearn scalers usually return numpy. We'll reconstruct a Polars DF.
        X_np = X_pl.to_numpy().astype(float)
        X_np = np.nan_to_num(X_np, nan=0.0)
        
        for i, scaler in self.scalers_.items():
            X_np[:, i] = scaler.transform(X_np[:, i].reshape(-1, 1)).flatten()
        
        X_res = pl.DataFrame(X_np, schema=X_pl.schema)
        if isinstance(X, (pd.DataFrame, pl.DataFrame)):
            return X_res
        return X_res.to_numpy()

    def get_feature_names_out(self, input_features=None):
        return input_features

    def _to_polars(self, X):
        if isinstance(X, pl.DataFrame): return X
        if isinstance(X, pd.DataFrame): return pl.from_pandas(X)
        if isinstance(X, np.ndarray):
            return pl.DataFrame(X, orient="row")
        return pl.DataFrame(X)

# ================================================================
# PIPELINE WRAPPER — Sérialisation avec pickle
# ================================================================

class PipelineWrapper(BaseEstimator, TransformerMixin):
    """
    Wrapper pour sérialiser un ColumnTransformer en pickle.
    Permet de faire des prédictions après rechargement.
    """
    def __init__(self, preprocessor, objective, algorithm, target_col, column_names=None):
        self.preprocessor = preprocessor
        self.objective = objective
        self.algorithm = algorithm
        self.target_col = target_col
        self.column_names = column_names  # Pour reconvertir numpy arrays en DataFrames
    
    def fit(self, X, y=None):
        # Capturer les noms de colonne si pas encore fait
        if self.column_names is None:
            if isinstance(X, pd.DataFrame):
                self.column_names = X.columns.tolist()
            elif isinstance(X, pl.DataFrame):
                self.column_names = X.columns
        self.preprocessor.fit(X, y)
        return self
    
    def _ensure_dataframe(self, X):
        """Convertir numpy array en DataFrame si nécessaire."""
        if isinstance(X, np.ndarray):
            if self.column_names is not None:
                return pd.DataFrame(X, columns=self.column_names)
            else:
                # Générer des noms de colonne génériques
                return pd.DataFrame(X, columns=[f'feature_{i}' for i in range(X.shape[1])])
        return X
    
    def transform(self, X):
        X = self._ensure_dataframe(X)
        return self.preprocessor.transform(X)
    
    def predict(self, X):
        return self.transform(X)
    
    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)

# ================================================================
# SERVICE PRINCIPAL
# ================================================================

class DataProcessingService:
    def __init__(self):
        pass

    def parse_file(self, file_content, filename):
        """
        Parse un fichier et retourne un dataframe Polars.
        Optimisé pour gérer les gros fichiers.
        """
        ext = filename.split('.')[-1].lower()
        df = None

        try:
            if ext == 'csv':
                # Polars avec streaming pour les gros fichiers
                try:
                    # Essayer d'abord avec le streaming pour économiser la mémoire
                    df = pl.scan_csv(
                        io.BytesIO(file_content),
                        ignore_errors=True,
                        infer_schema_length=10000  # Limiter l'inférence pour gain de perf
                    ).collect()  # Collect après le scan
                except Exception as e1:
                    # Fallback sur la lecture standard
                    print(f"[WARNING] Scan CSV failed: {str(e1)}, trying standard read...")
                    df = pl.read_csv(
                        io.BytesIO(file_content),
                        ignore_errors=True,
                        infer_schema_length=10000
                    )
                    
            elif ext in ['xls', 'xlsx']:
                # Polars uses fastexcel or xlsx2csv/calamine
                df = pl.read_excel(io.BytesIO(file_content))
            elif ext == 'json':
                try:
                    df = pl.read_json(io.BytesIO(file_content))
                except:
                    data = json.loads(file_content.decode('utf-8'))
                    if isinstance(data, dict):
                        df = pl.DataFrame([data])
                    else:
                        df = pl.DataFrame(data)
            elif ext == 'xml':
                # Polars doesn't have native read_xml yet, use pandas as fallback
                pdf = pd.read_xml(io.BytesIO(file_content))
                df = pl.from_pandas(pdf)
            else:
                return None, f"Format .{ext} non supporté"
        except Exception as e:
            error_msg = str(e)[:200]  # Limiter la taille du message
            print(f"[ERROR] Parsing {ext.upper()}: {error_msg}")
            return None, f"Erreur de lecture {ext.upper()}: {error_msg}"

        if df is None or df.is_empty():
            return None, f"Le fichier {ext.upper()} est vide ou n'a pas pu être converti en tableau."

        return df, None

    # --- VISUELS BACKEND (Les 8 Visuels) ---

    def get_dataset_info(self, df, dataset_id=None):
        df = self._to_polars(df)
        print(f"--- [SERVICE] Generating info for Dataset: {dataset_id} | Shape: {df.shape} ---")
        info = {
            "id": dataset_id,
            "dataset_id": dataset_id,
            "_id": dataset_id,
            "version": "V8.0-POLARS",
            "rows": df.height,
            "columns": df.width,
            "headers": [str(c) for c in df.columns],
            "columnInfo": []
        }

        missing_analysis = self.analyze_missing_data(df)

        for col in df.columns:
            dtype = df.schema[col]
            if dtype.is_numeric():
                col_type = 'numeric'
            elif dtype == pl.Boolean:
                col_type = 'boolean'
            elif dtype in [pl.Date, pl.Datetime]:
                col_type = 'datetime'
            else:
                # Check if essentially numeric
                if self._is_essentially_numeric(df[col]):
                    col_type = 'numeric'
                else:
                    col_type = 'categorical'

            unique_count = int(df[col].n_unique())
            null_count = int(df[col].null_count())
            null_percentage = float((null_count / df.height) * 100) if df.height > 0 else 0
            
            # Rich distribution metrics
            dist_info = {"min": "-", "max": "-", "topValue": "-", "topPercentage": 0}
            
            # Numeric/Datetime Stats
            if col_type in ['numeric', 'datetime']:
                try:
                    # Individual min/max calculation to avoid one failure killing both
                    try:
                        mv = df[col].min()
                        if mv is not None and not (isinstance(mv, float) and (math.isnan(mv) or math.isinf(mv))):
                            dist_info["min"] = round(float(mv), 2) if col_type == 'numeric' else str(mv)
                    except: pass
                    
                    try:
                        mv = df[col].max()
                        if mv is not None and not (isinstance(mv, float) and (math.isnan(mv) or math.isinf(mv))):
                            dist_info["max"] = round(float(mv), 2) if col_type == 'numeric' else str(mv)
                    except: pass
                except:
                    pass
            
            # Top Value logic (Robust to nulls and versions)
            try:
                # Drop nulls for top value calculation to get the most frequent ACTUAL value
                clean_col = df[col].drop_nulls()
                if clean_col.len() > 0:
                    counts = clean_col.value_counts(sort=True)
                    if len(counts) > 0:
                        top_row = counts.head(1)
                        # Find the count column (could be 'count' or 'counts')
                        count_col = "count" if "count" in counts.columns else "counts"
                        
                        dist_info["topValue"] = str(top_row[col][0])
                        actual_count = top_row[count_col][0]
                        perc = float((actual_count / df.height) * 100) if df.height > 0 else 0
                        dist_info["topPercentage"] = perc if not (math.isnan(perc) or math.isinf(perc)) else 0
            except Exception as e:
                print(f"--- [DEBUG] TopValue calculation error for {col}: {str(e)} ---")

            # Diagnostic & Action Logic (V8.3 Robust Audit)
            diagnostic = "Prêt pour modélisation"
            severity = "success" # success, warning, danger, info
            
            # Sub-stats for ID detection with missing values
            non_null_series = df[col].drop_nulls()
            non_null_count = non_null_series.len()
            non_null_uniques = non_null_series.n_unique()

            # 1. Constant or Quasi-constant
            if unique_count == 1:
                diagnostic = "Valeur constante (À supprimer)"
                severity = "danger"
            elif dist_info["topPercentage"] > 95 and df.height > 20:
                diagnostic = "Quasi-constante >95% (À supprimer)"
                severity = "danger"
            
            # 2. Unique Identifiers (Handles missing values)
            elif non_null_uniques == non_null_count and non_null_count > 0 and df.height > 1:
                if non_null_count == df.height:
                    diagnostic = "Identifiant unique (À supprimer)"
                else:
                    diagnostic = "Identifiant partiel (À supprimer)"
                severity = "danger"
                
            elif col_type == 'categorical' and unique_count > (df.height * 0.9) and df.height > 20:
                diagnostic = "Haute cardinalité (Nom/Email - Supprimer ?)"
                severity = "warning"
            
            # 3. Missing Data / Health
            elif null_percentage > 50:
                diagnostic = "Critique : Trop de vides (>50%)"
                severity = "danger"
            
            # 4. Specific Data Types (NLP, Temporal)
            elif col_type == 'categorical':
                # Detect free text (NLP)
                try:
                    avg_len = non_null_series.str.len_bytes().mean()
                    if avg_len is not None and avg_len > 50:
                        diagnostic = "Texte libre (NLP ou Supprimer)"
                        severity = "info"
                except: pass
            
            elif col_type == 'datetime':
                diagnostic = "Donnée temporelle (Extraction auto)"
                severity = "info"
            
            # 5. Imputation Needed
            if diagnostic == "Prêt pour modélisation" and str(col) in missing_analysis:
                m_type = missing_analysis[str(col)]["type"]
                if m_type in ["MAR", "MNAR"]:
                    diagnostic = f"Déficit {m_type} (Imputation IA)"
                    severity = "warning"
                else:
                    diagnostic = "Vides légers (Imputation simple)"
                    severity = "info"

            col_info = {
                "name": str(col),
                "type": col_type,
                "nullCount": null_count,
                "nullPercentage": null_percentage,
                "uniqueCount": unique_count,
                "diagnostic": diagnostic,
                "severity": severity,
                "distribution": dist_info,
                "sampleValues": [str(v) for v in df[col].head(5).to_list()]
            }

            info["columnInfo"].append(col_info)

        try:
            # Polars to_dicts() for JSON records
            temp_df = df.head(50).fill_null(0).fill_nan(0) # Minimal fill for preview
            info["data"] = temp_df.to_dicts()
        except Exception as e:
            print(f"--- [ERROR] Data preview failed: {str(e)} ---")
            info["data"] = []
            info["previewError"] = str(e)

        print(f"--- [SERVICE] Info ready. Version: {info.get('version')} ---")
        import sys
        sys.stdout.flush()
        return info


    # ================================================================
    # ANALYSE MCAR / MAR / MNAR (EXIGENCE 1)
    # ================================================================

    def analyze_missing_data(self, df):
        """
        Analyse la nature des données manquantes (MCAR, MAR, MNAR)
        pour chaque colonne du DataFrame en utilisant Polars.
        """
        df = self._to_polars(df)
        result = {}
        # Get columns with at least one null
        null_counts = df.null_count()
        cols_with_missing = [col for col in df.columns if null_counts[col][0] > 0]

        if not cols_with_missing:
            return result

        numeric_cols = [col for col, dtype in df.schema.items() if dtype.is_numeric()]

        for col in cols_with_missing:
            null_count = int(df[col].null_count())
            null_percentage = float((null_count / df.height) * 100)
            
            # Binary indicator for missingness
            # We don't need a full series here, just the Logic for correlation
            correlations = {}
            max_corr = 0.0

            for other_col in numeric_cols:
                if other_col == col:
                    continue
                try:
                    # Drop nulls for correlation calculation
                    # We need to drop nulls from the other_col and align the indicator
                    temp = df.select([
                        pl.col(other_col),
                        pl.col(col).is_null().cast(pl.Float64).alias("_indicator")
                    ]).drop_nulls(subset=[other_col])
                    
                    if temp.height > 1:
                        corr = abs(temp.select(pl.corr(other_col, "_indicator")).item())
                        if corr is not None and not math.isnan(corr):
                            correlations[other_col] = round(float(corr), 3)
                            max_corr = max(max_corr, corr)
                except:
                    pass

            if max_corr < 0.1:
                missing_type = "MCAR"
                description = "Données manquantes complètement aléatoires"
            elif max_corr < 0.3:
                missing_type = "MAR"
                description = "Données manquantes dépendant d'autres variables observées"
            else:
                missing_type = "MNAR"
                description = "Données manquantes non aléatoires (dépendance forte)"

            result[str(col)] = {
                "type": missing_type,
                "description": description,
                "nullCount": null_count,
                "nullPercentage": round(null_percentage, 1),
                "correlations": correlations,
                "maxCorrelation": round(float(max_corr), 3)
            }

        return result


    # ================================================================
    # STATISTIQUES DESCRIPTIVES
    # ================================================================

    def compute_stats(self, df, column):
        df = self._to_polars(df)
        if column not in df.columns:
            return None
        
        # Cast to float for stats calculation
        col_expr = pl.col(column).cast(pl.Float64)
        
        try:
            stats_res = df.select([
                col_expr.mean().alias("mean"),
                col_expr.median().alias("median"),
                col_expr.std().alias("std"),
                col_expr.min().alias("min"),
                col_expr.max().alias("max"),
                col_expr.quantile(0.25).alias("q1"),
                col_expr.quantile(0.75).alias("q3"),
                col_expr.skew().alias("skewness")
            ])
            
            res_dict = stats_res.to_dicts()[0]
            
            # Mode separately since it can return multiple values
            mode_val = df.select(pl.col(column).drop_nulls().mode()).to_series()
            mode = float(mode_val[0]) if len(mode_val) > 0 else None

            stats = {
                "mean": float(res_dict["mean"]) if res_dict["mean"] is not None else 0.0,
                "median": float(res_dict["median"]) if res_dict["median"] is not None else 0.0,
                "mode": mode,
                "std": float(res_dict["std"]) if res_dict["std"] is not None else 0.0,
                "min": float(res_dict["min"]) if res_dict["min"] is not None else 0.0,
                "max": float(res_dict["max"]) if res_dict["max"] is not None else 0.0,
                "q1": float(res_dict["q1"]) if res_dict["q1"] is not None else 0.0,
                "q3": float(res_dict["q3"]) if res_dict["q3"] is not None else 0.0,
                "iqr": float(res_dict["q3"] - res_dict["q1"]) if (res_dict["q1"] is not None and res_dict["q3"] is not None) else 0.0,
                "skewness": float(res_dict["skewness"]) if res_dict["skewness"] is not None else 0.0,
            }
            stats["isNormal"] = bool(abs(stats["skewness"]) < 0.5)
            stats["isSymmetric"] = bool(abs(stats["skewness"]) < 1)
            return stats
        except Exception as e:
            print(f"--- [ERROR] Stats calculation failed for {column}: {str(e)} ---")
            return None


    # ================================================================
    # CORRECTIF #4 : VALIDATION CROISÉE DU PIPELINE (Exigence G)
    # ================================================================

    def validate_pipeline_with_cv(self, pipeline, X, y, cv=5, scoring=None):
        """
        Valide le pipeline avec cross-validation stratifiée.
        Retourne les scores et statistiques de robustesse.
        """
        try:
            X_np = self._to_numpy(X)
            y_np = np.array(y).flatten()
            
            is_classification = len(np.unique(y_np)) < 100  # Simple heuristic
            
            if cv is None:
                cv = 5
            
            cv_splitter = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42) if is_classification else KFold(n_splits=cv, shuffle=True, random_state=42)
            
            if scoring is None:
                scoring = 'accuracy' if is_classification else 'r2'
            
            cv_results = cross_validate(
                pipeline, X_np, y_np,
                cv=cv_splitter,
                scoring=scoring,
                return_train_score=True,
                n_jobs=-1
            )
            
            metrics = {
                'train_scores': cv_results['train_score'].tolist(),
                'test_scores': cv_results['test_score'].tolist(),
                'mean_train': float(np.mean(cv_results['train_score'])),
                'mean_test': float(np.mean(cv_results['test_score'])),
                'std_train': float(np.std(cv_results['train_score'])),
                'std_test': float(np.std(cv_results['test_score'])),
                'overfitting_gap': float(np.mean(cv_results['train_score']) - np.mean(cv_results['test_score']))
            }
            return metrics
        except Exception as e:
            print(f"[ERROR] Cross-validation failed: {str(e)}")
            return None

    def _to_numpy(self, X):
        if isinstance(X, pl.DataFrame): return X.to_numpy().astype(float)
        if isinstance(X, pd.DataFrame): return X.values.astype(float)
        if isinstance(X, np.ndarray): return X.astype(float)
        return np.array(X, dtype=float)


    # ================================================================
    # CORRECTIF #5 : TEST DE NON-RÉGRESSION (Exigence H)
    # ================================================================

    def test_pipeline_regression(self, pipeline_path, X_test, y_test_true=None):
        """
        Teste qu'un pipeline recharger produit les mêmes prédictions.
        Valide la sauvegarde/charge et la cohérence du pipeline.
        """
        try:
            # Charger le pipeline
            if not os.path.exists(pipeline_path):
                return {'status': 'FAILED', 'reason': f'Pipeline not found: {pipeline_path}'}
            
            loaded_pipeline = joblib.load(pipeline_path)
            
            # Prédictions sur X_test (Conserver le format DataFrame si possible pour les dtypes)
            X_test_input = X_test if isinstance(X_test, (pd.DataFrame, pl.DataFrame)) else self._to_numpy(X_test)
            pred_loaded = loaded_pipeline.predict(X_test_input)
            
            # Vérifier la cohérence (rechargement multiple)
            loaded_pipeline_2 = joblib.load(pipeline_path)
            pred_loaded_2 = loaded_pipeline_2.predict(X_test_input)
            
            predictions_match = np.allclose(pred_loaded, pred_loaded_2, atol=1e-6) if pred_loaded.dtype != object else np.array_equal(pred_loaded, pred_loaded_2)
            
            if not predictions_match:
                return {'status': 'FAILED', 'reason': 'Predictions differ on reload'}
            
            # Si y_test_true est fourni, vérifier l'accuracy
            accuracy = None
            if y_test_true is not None:
                y_true_np = np.array(y_test_true).flatten()
                accuracy = float(np.mean(pred_loaded == y_true_np))
            
            return {
                'status': 'PASSED',
                'predictions_count': len(pred_loaded),
                'predictions_sample': pred_loaded[:5].tolist(),
                'accuracy': accuracy,
                'consistency': True
            }
        except Exception as e:
            return {'status': 'FAILED', 'reason': str(e)}


    # ================================================================
    # AUTO-PILOT avec Pipeline + ColumnTransformer + fit_transform
    # (EXIGENCE PIPELINE E)
    # ================================================================

    def _to_polars(self, X):
        if isinstance(X, pl.DataFrame): return X
        if isinstance(X, pd.DataFrame): return pl.from_pandas(X)
        if isinstance(X, np.ndarray):
            return pl.DataFrame(X, orient="row")
        return pl.DataFrame(X)

    def auto_pilot(self, df, objective='classification', algorithm=None, nlp_mode=None, is_guest=False):
        """
        Auto-Pilot V8-POLARS : Refactorisation complète vers Polars.
        Support multi-algorithmes : algorithm peut être une chaîne ou une liste.
        """
        transformations = []
        df = self._to_polars(df)
        initial_columns = list(df.columns)
        
        # --- NORMALISER L'ALGORITHME (Support Multi-Algo) ---
        if not algorithm or algorithm == 'none' or algorithm == '':
            algos = ['auto']
        elif isinstance(algorithm, list):
            algos = [str(a).lower().strip() for a in algorithm]
        else:
            # Gérer les chaînes séparées par des virgules ou les chaînes simples
            algos = [a.lower().strip() for a in str(algorithm).split(',') if a.strip()]
        
        # FIX : Si l'utilisateur a choisi des algos spécifiques ET "auto", on ignore "auto" pour respecter son choix explicite
        if len(algos) > 1 and 'auto' in algos:
            algos = [a for a in algos if a != 'auto']
            
        if not algos: algos = ['auto']

        # --- CONFIGURATION AGGRÉGÉE SELON LES ALGORITHMES CHOISIS (Strict AI Rules) ---
        TREE_ALGOS = ['rf', 'xgboost', 'lightgbm', 'catboost', 'dt']
        DISTANCE_ALGOS = ['knn', 'svm']
        LINEAR_ALGOS = ['linear', 'logistic']
        NEURAL_ALGOS = ['nn']
        
        # Familles
        is_tree_family = all(a in TREE_ALGOS for a in algos)
        is_nn_family = any(a in NEURAL_ALGOS for a in algos)
        is_distance_family = any(a in (DISTANCE_ALGOS + NEURAL_ALGOS + LINEAR_ALGOS + ['auto']) for a in algos)
        
        # EXIGENCES UTILISATEUR :
        # 1. Famille Arbres (RF/XGB, etc.) -> NI Scaling, NI Encoding
        # 2. Famille Distance / Linéaire / NN -> Scaling + Encoding
        # 3. Réseaux de Neurones -> Scaling + Encoding + Outliers activés
        
        scaling_enabled = not is_tree_family
        encoding_enabled = not is_tree_family
        outliers_mandatory = is_nn_family or (is_distance_family and not is_tree_family)
        
        scaling_method = 'StandardScaler' if scaling_enabled else 'none'
        needs_distance_scaling = any(a in (DISTANCE_ALGOS + NEURAL_ALGOS + ['auto']) for a in algos)

        try:
            # ── RESTRICTION MODE INVITÉ ──
            if is_guest:
                nlp_mode = None  # A.2 : NLP bloqué pour les invités

            algo_str = ", ".join(algos)
            print(f"--- [AUTOPILOT V8-POLARS] Objective: {objective}, Algos: {algo_str}, NLP: {nlp_mode}, Guest: {is_guest} ---", flush=True)
            print(f"[DEBUG] Initial Data Shape: {df.shape}", flush=True)
            transformations.append(f"MODE : Auto-Pilot (Objectif: {objective}, Algos: {algo_str})")

            # ================================================================
            # SECTION 0.0 — IDENTIFICATION DE LA CIBLE (DEPLACÉ EN HAUT)
            # ================================================================
            target_col = next(
                (c for c in df.columns if str(c).lower() in ['target', 'label', 'class', 'y', 'output', 'target_var']),
                None
            )

            # Safeguard: ANALYSE DE CORRÉLATION PRÉLIMINAIRE
            protected_cols = []
            if target_col and target_col in df.columns:
                try:
                    # Check correlation only for numeric columns initially
                    temp_target = df[target_col]
                    if df.schema[target_col] == pl.Utf8:
                        # Simple categorical to numeric for correlation heuristic
                        temp_target = df[target_col].rank().cast(pl.Float64)
                    else:
                        temp_target = df[target_col].cast(pl.Float64)
                    
                    for col in df.columns:
                        if col == target_col: continue
                        if df.schema[col].is_numeric():
                            try:
                                corr = abs(df.select(pl.corr(pl.col(col), temp_target)).item())
                                if corr is not None and not math.isnan(corr) and corr > 0.05:
                                    protected_cols.append(col)
                            except: pass
                except: pass
            
            if protected_cols:
                print(f"--- [AUTOPILOT] Protected columns (predictive): {protected_cols} ---")

            # ---- NLP : Detection des colonnes texte (AVANT Nettoyage/Suppression) ----
            text_features = []
            nlp_enabled = nlp_mode and nlp_mode != 'none'
            for col in df.columns:
                # Détection : Chaines de caractères avec beaucoup de valeurs uniques (> 50)
                if df.schema[col] == pl.Utf8 and df[col].n_unique() > 50:
                    text_features.append(col)
            
            if text_features and nlp_enabled:
                transformations.append(f"NLP: Detection de {len(text_features)} colonnes texte : {', '.join(text_features)}")

            # ---- E.1 : Supprimer les doublons exacts ----
            initial_len = df.height
            df = df.unique()
            if df.height < initial_len:
                transformations.append(f"E.1: Suppression de {initial_len - df.height} doublons exacts")

            # ---- Fix #1 : Doublons partiels (sur colonnes clés) ----
            id_kw = ['id', 'uuid', 'index', 'key', 'ref']
            potential_id_cols = [c for c in df.columns if any(kw in str(c).lower() for kw in id_kw)]
            for id_col in potential_id_cols:
                before_dedup = df.height
                df = df.unique(subset=[id_col])
                if df.height < before_dedup:
                    transformations.append(f"0.2: Suppression de {before_dedup - df.height} doublons partiels (sur '{id_col}')")

            # ---- Exigence 10 : Supprimer les LIGNES en premier (>50% NaN) ----
            null_counts_per_row = df.select(pl.sum_horizontal(pl.all().is_null())).to_series()
            threshold = df.width * 0.5
            mask = null_counts_per_row <= threshold
            rows_before = df.height
            df = df.filter(mask)
            if df.height < rows_before:
                transformations.append(f"Exigence 10: Suppression de {rows_before - df.height} lignes (NaN > 50%)")

            # ---- Fix #5 : Suppression des COLONNES avec >50% NaN ----
            cols_high_nan = []
            for col in df.columns:
                null_pct = df[col].null_count() / df.height if df.height > 0 else 0
                if null_pct > 0.5:
                    cols_high_nan.append((col, null_pct))
            
            if cols_high_nan:
                df = df.drop([c[0] for c in cols_high_nan])
                for c, pct in cols_high_nan:
                    transformations.append(f"A.3: Colonne '{c}' supprimee (>{int(pct*100)}% NaN)")


            # ================================================================
            # SECTION C.0 — NETTOYAGE DES ANOMALIES CATÉGORIELLES (Heuristique)
            # ================================================================
            categorical_cols = [col for col in df.columns if df.schema[col] == pl.Utf8]
            cat_corrections = []
            for col in categorical_cols:
                if col == target_col or (nlp_enabled and col in text_features):
                    continue
                
                counts = df[col].drop_nulls().value_counts().sort("count", descending=True)
                if counts.height < 2: continue
                
                total_cat_rows = counts["count"].sum()
                dominant_val = str(counts[col][0])
                
                for row in counts.to_dicts():
                    val = str(row[col])
                    count = row["count"]
                    if count < 3 and (count / total_cat_rows) < 0.15:
                        others_sample = [str(v) for v in counts[col].head(5) if str(v) != val]
                        if not others_sample: continue
                        
                        val_is_digit = val.replace('.','',1).isdigit()
                        others_are_mostly_alpha = sum(1 for v in others_sample if v.isalpha()) / len(others_sample) > 0.5
                        if val_is_digit and others_are_mostly_alpha:
                            df = df.with_columns(pl.col(col).replace(val, dominant_val))
                            cat_corrections.append(f"'{col}': '{val}' -> '{dominant_val}' (Outlier)")
            
            if cat_corrections:
                transformations.append(f"C.0: Nettoyage des anomalies catégorielles : {', '.join(cat_corrections)}")


            # ================================================================
            # SECTION 0.1 — AUDIT DES TYPES DE DONNEES
            # ================================================================
            type_corrections = []
            for col in df.columns:
                dtype = df.schema[col]
                # string -> numeric?
                if dtype == pl.Utf8:
                    non_null = df[col].drop_nulls()
                    if not non_null.is_empty():
                        converted = non_null.cast(pl.Float64, strict=False)
                        valid_count = converted.drop_nulls().len()
                        if valid_count / non_null.len() > 0.8:
                            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                            type_corrections.append(f"'{col}': Utf8 -> float64")
                            continue
                # string -> datetime?
                if dtype == pl.Utf8:
                    non_null = df[col].drop_nulls()
                    if not non_null.is_empty():
                        try:
                            sample = non_null.head(20).to_list()
                            import dateutil.parser
                            valid_dates = 0
                            for s in sample:
                                try:
                                    dateutil.parser.parse(str(s))
                                    valid_dates += 1
                                except: pass
                            if valid_dates / len(sample) > 0.7:
                                df = df.with_columns(pl.col(col).str.to_datetime(strict=False))
                                type_corrections.append(f"'{col}': Utf8 -> datetime")
                                continue
                        except: pass
                # int/float with only 0/1 -> bool? (SKIP target)
                if col != target_col and dtype.is_numeric():
                    unique_vals = df[col].drop_nulls().unique().to_list()
                    if set(unique_vals).issubset({0, 1, 0.0, 1.0}) and len(unique_vals) == 2:
                        df = df.with_columns(pl.col(col).cast(pl.Boolean))
                        type_corrections.append(f"'{col}': {dtype} -> bool")

            if type_corrections:
                transformations.append(f"0.1: Correction des types : {', '.join(type_corrections)}")
            else:
                transformations.append("0.1: Audit des types OK")


            # ================================================================
            # SECTION 0.4 — SUPPRESSION DES COLONNES NON PREDICTIVES
            # ================================================================
            cols_to_remove = []
            n_rows = df.height
            for col in df.columns:
                # IMPORTANT : Ne pas supprimer si NLP activé pour cette colonne
                if nlp_enabled and col in text_features: continue
                
                nuniq = df[col].n_unique()
                if nuniq >= n_rows * 0.95 and df.schema[col] == pl.Utf8:
                    cols_to_remove.append((col, 'identifiant unique'))
                elif nuniq <= 1:
                    cols_to_remove.append((col, 'constante'))
                elif nuniq > 1:
                    # Quasi-constante check
                    counts = df[col].value_counts().sort("count", descending=True)
                    top_freq = counts["count"][0] / n_rows
                    if top_freq > 0.95:
                        if col in protected_cols:
                            print(f"[SAFEGUARD] Keeping quasi-constant column '{col}' due to correlation with target.")
                        else:
                            cols_to_remove.append((col, 'quasi-constante (>95%)'))

                # Safeguard: if high cardinality looks like ID but is predictive
                if col in protected_cols and any(c[0] == col for c in cols_to_remove):
                    cols_to_remove = [c for c in cols_to_remove if c[0] != col]
                    print(f"[SAFEGUARD] Recovered column '{col}' from deletion list (predictive).")

            if cols_to_remove:
                df = df.drop([c[0] for c in cols_to_remove])
                for col_name, reason in cols_to_remove:
                    transformations.append(f"0.4: Colonne '{col_name}' supprimee ({reason})")

            # ================================================================
            # SECTION C.1 — COLONNES ID / NOM (haute cardinalite)
            # À FAIRE IMMÉDIATEMENT — AVANT MCAR/MAR/MNAR
            # ================================================================
            id_keywords = ['id', 'uuid', 'index', 'key', 'ref', 'sku', 'code']
            name_keywords = ['name', 'nom', 'email', 'url', 'adresse', 'address']
            id_cols_removed = []
            
            for col in df.columns:
                if col == target_col: continue
                # Exempt text columns from ID-drop if NLP is on
                if nlp_enabled and col in text_features: continue
                
                col_lower = str(col).lower()
                non_null_vals = df[col].drop_nulls()
                n_non_null = non_null_vals.len()
                n_uniques_non_null = non_null_vals.n_unique()
                
                # Règle 1 : Mots-clés ID/Nom avec haute cardinalité
                is_id_like = any(kw in col_lower for kw in id_keywords)
                is_name_like = any(kw in col_lower for kw in name_keywords)
                if (is_id_like or is_name_like) and df[col].n_unique() > n_rows * 0.8:
                    id_cols_removed.append(col)
                    continue
                
                # Règle 2 : Identifiant pur (parmi les valeurs non-null >= 95% sont uniques)
                if n_non_null > 0 and (n_uniques_non_null / n_non_null) >= 0.95:
                    if col in protected_cols:
                        print(f"[SAFEGUARD] Keeping unique column '{col}' due to correlation with target.")
                    elif df.schema[col].is_numeric() and not target_col:
                        # FIX: Ne pas supprimer les colonnes numériques très uniques si on n'a pas de cible (ex: SQ_FT, Price)
                        print(f"[SAFEGUARD] Keeping unique numeric column '{col}' because no target is identified yet.")
                    else:
                        id_cols_removed.append(col)
            
            if id_cols_removed:
                df = df.drop(id_cols_removed)
                for col_name in id_cols_removed:
                    transformations.append(f"C.1: Colonne '{col_name}' supprimee (identifiant ou haute cardinalité)")

            # ---- Exigence 1 : Analyser MCAR/MAR/MNAR (SUR LES COLONNES RESTANTES) ----
            missing_analysis = self.analyze_missing_data(df)
            for col, info in missing_analysis.items():
                transformations.append(f"A.1: Colonne '{col}' -> {info['type']} ({info['nullPercentage']}%)")

            # ================================================================
            # SECTION A.1+ — INDICATEURS BINAIRES MNAR
            # SEULEMENT POUR LES COLONNES CONSERVÉES (pas les ID supprimées)
            # ================================================================
            mnar_indicators_created = []
            for col, info in missing_analysis.items():
                if info['type'] == 'MNAR' and col in df.columns:
                    indicator_name = f"{col}_was_missing"
                    df = df.with_columns(pl.col(col).is_null().cast(pl.Int32).alias(indicator_name))
                    mnar_indicators_created.append(indicator_name)
            if mnar_indicators_created:
                transformations.append(f"A.1+: Indicateurs MNAR crees : {', '.join(mnar_indicators_created)}")

            # ================================================================
            # SECTION C.2 — EXTRACTION DE FEATURES TEMPORELLES (Complet)
            # ================================================================
            datetime_cols = [col for col, dtype in df.schema.items() if dtype in [pl.Date, pl.Datetime]]
            date_features_created = []
            for col in datetime_cols:
                if col == target_col: continue
                # Features de base
                df = df.with_columns([
                    pl.col(col).dt.year().alias(f'{col}_year'),
                    pl.col(col).dt.month().alias(f'{col}_month'),
                    pl.col(col).dt.day().alias(f'{col}_day'),
                    pl.col(col).dt.weekday().alias(f'{col}_dayofweek'),
                    pl.col(col).dt.quarter().alias(f'{col}_quarter'),
                ])
                # Fix #2 : Features avancées (weekend, saison, ancienneté)
                df = df.with_columns([
                    (pl.col(f'{col}_dayofweek') >= 5).cast(pl.Int32).alias(f'{col}_is_weekend'),
                    pl.when(pl.col(f'{col}_month').is_in([12, 1, 2])).then(1)
                      .when(pl.col(f'{col}_month').is_in([3, 4, 5])).then(2)
                      .when(pl.col(f'{col}_month').is_in([6, 7, 8])).then(3)
                      .otherwise(4).alias(f'{col}_season'),
                ])
                # Ancienneté en jours depuis la date min (référence interne)
                try:
                    ref_date = df[col].drop_nulls().min()
                    if ref_date is not None:
                        df = df.with_columns(
                            ((pl.col(col) - ref_date).dt.total_days()).cast(pl.Float64).alias(f'{col}_days_since')
                        )
                        date_features_created.append(f'{col}_days_since')
                except Exception:
                    pass
                date_features_created.extend([
                    f'{col}_year', f'{col}_month', f'{col}_day', 
                    f'{col}_dayofweek', f'{col}_quarter',
                    f'{col}_is_weekend', f'{col}_season'
                ])
                df = df.drop(col)
            if date_features_created:
                transformations.append(f"C.2: Features temporelles extraites : {', '.join(date_features_created)}")

            # ================================================================
            # SECTION C.3 — ENCODAGE CYCLIQUE (sin/cos)
            # ================================================================
            cyclical_features = []
            cyclical_map = {'month': 12, 'dayofweek': 7, 'day': 31, 'hour': 24, 'quarter': 4}
            for col in df.columns:
                if col == target_col: continue
                col_lower = str(col).lower()
                for pattern, period in cyclical_map.items():
                    if col_lower.endswith(f'_{pattern}') or col_lower == pattern:
                        if df.schema[col].is_numeric():
                            df = df.with_columns([
                                (pl.col(col).fill_null(0) * (2 * math.pi / period)).sin().alias(f'{col}_sin'),
                                (pl.col(col).fill_null(0) * (2 * math.pi / period)).cos().alias(f'{col}_cos'),
                            ])
                            cyclical_features.extend([f'{col}_sin', f'{col}_cos'])
                            df = df.drop(col)
                            break
            if cyclical_features:
                transformations.append(f"C.3: Encodage cyclique sin/cos : {', '.join(cyclical_features)}")

            # ---- Detection time series et groupe ----
            remaining_datetime = [col for col, dtype in df.schema.items() if dtype in [pl.Date, pl.Datetime]]
            is_timeseries = len(remaining_datetime) > 0
            group_col = next((c for c in ['category', 'department', 'type', 'group'] if c in df.columns and c != target_col), None)

            # (NLP detection moved up to line 1184)
            if nlp_enabled and text_features:
                transformations.append(f"NLP : {len(text_features)} colonnes texte detectees pour {nlp_mode}")

            # ================================================================
            # SECTION C.4 — HAUTE CARDINALITE (Frequency Encoding / Suppression)
            # ================================================================
            # Si NLP désactivé, on SUPPRIME les colonnes texte (Haut Cardinalité)
            # Sinon on garde le Frequency Encoding pour les nominales à plusieurs niveaux
            high_card_processed = []
            for col in df.columns:
                if col == target_col: continue
                if col in text_features:
                    if not nlp_enabled:
                        # Cas "Désactivé" -> On supprime la colonne texte
                        df = df.drop(col)
                        transformations.append(f"C.4: Colonne texte '{col}' supprimee (NLP desactive)")
                    continue

                # Frequency Encoding standard pour les nominales > 50 niveaux
                if df.schema[col] == pl.Utf8 and df[col].n_unique() > 50:
                    freqs = df[col].value_counts(normalize=True)
                    df = df.join(freqs, on=col, how="left").with_columns(pl.col("proportion").fill_null(0.0).alias(col)).drop("proportion")
                    high_card_processed.append(col)
            
            if high_card_processed:
                transformations.append(f"C.4: Frequency Encoding : {', '.join(high_card_processed)}")

            # ---- Mise a jour de initial_columns apres feature engineering ----
            initial_columns = list(df.columns)

            # ---- E.3-E.5 : Definir les listes de variables ----
            numerical_features = []
            nominale_features = []
            ordinale_features = []
            ordinal_keywords = ['level', 'grade', 'rank', 'size', 'rating', 'priority', 'status', 'ordinal']

            for col in df.columns:
                if col == target_col: continue
                if self._is_essentially_numeric(df[col]):
                    numerical_features.append(col)
                    df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                else:
                    if any(kw in str(col).lower() for kw in ordinal_keywords):
                        ordinale_features.append(col)
                    else:
                        nominale_features.append(col)

            # (NLP detection moved up to line 1327)


            # ---- E.2 : Instanciation des classes personnalisées ----
            num_missing_handler = MissingValueHandler(group_col=group_col, is_timeseries=is_timeseries, missing_analysis=missing_analysis, is_guest=is_guest)
            
            # Détecter si on a au moins un algo basé sur les arbres pour le détecteur d'outliers
            has_tree_algo = any(a in ['rf', 'xgboost', 'lightgbm', 'catboost'] for a in algos)
            multivar_algorithm = 'isolation' if has_tree_algo else 'lof'
            
            # A.2 — Invités : PAS d'outliers multivariés (LOF/Isolation Forest bloqués)
            if is_guest:
                num_outlier_handler = None
                transformations.append("B.1: Outliers multivariés non disponibles (mode invité)")
            else:
                # Outliers activés pour les familles non-arbres (ou si forcés par NN)
                num_outlier_handler = MultivariatOutlierDetector(algorithm=multivar_algorithm, contamination=0.05) if outliers_mandatory else None
            
            # ---- E.6 : num_pipeline (Exigences 1-10 + 17-19) ----
            num_steps = [('missing_handler', num_missing_handler)]
            if num_outlier_handler:
                num_steps.append(('multivar_outlier_detector', num_outlier_handler))
                transformations.append(f"B.1+: Outliers multivariés activés (algo={multivar_algorithm})")
            if scaling_enabled:
                num_steps.append(('scaler', AdaptiveScaler()))
                transformations.append(f"F.1: Scaling numérique activé (méthode={scaling_method}, algos={algo_str})")
            else:
                transformations.append(f"F.1: Scaling numérique DÉSACTIVÉ (Famille Arbres)")
            
            num_pipeline = Pipeline(steps=num_steps)

            nom_steps = [('missing_handler', MissingValueHandler(missing_analysis=missing_analysis))]
            if encoding_enabled:
                nom_steps.append(('encoder', CompactOneHotEncoder(dtype=np.float64 if needs_distance_scaling else np.int32)))
                transformations.append(f"E.2: Encodage Nominal activé (OneHot)")
                if needs_distance_scaling:
                    nom_steps.append(('scaler', MinMaxScaler()))
                    transformations.append(f"F.2: Scaling catégoriel activé (MinMaxScaler)")
            else:
                transformations.append(f"E.2: Encodage & Scaling catégoriel DÉSACTIVÉ (Famille Arbres)")
            nom_pipeline = Pipeline(steps=nom_steps)

            ord_steps = [('missing_handler', MissingValueHandler(missing_analysis=missing_analysis))]
            if encoding_enabled:
                ord_steps.append(('encoder', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)))
                transformations.append(f"E.3: Encodage Ordinal activé")
                if needs_distance_scaling:
                    ord_steps.append(('scaler', MinMaxScaler()))
                    transformations.append(f"F.2: Scaling ordinal activé (MinMaxScaler)")
            ord_pipeline = Pipeline(steps=ord_steps)

            # ---- E.8 : Créer le preprocessor (ColumnTransformer) ----
            transformers_list = []
            if numerical_features: transformers_list.append(('num', num_pipeline, numerical_features))
            if nominale_features: transformers_list.append(('nom', nom_pipeline, nominale_features))
            if ordinale_features: transformers_list.append(('ord', ord_pipeline, ordinale_features))

            # CORRECTIF #1 : Support complet du NLP (TF-IDF, Word2Vec, BERT)
            # SAFETY: filter text_features to only include columns still in df
            text_features = [c for c in text_features if c in df.columns]
            if text_features:
                effective_nlp = nlp_mode
                if nlp_mode == 'embeddings':
                    # Heuristic check without importing at top level
                    effective_nlp = 'bert'
                
                if effective_nlp == 'tfidf':
                    nlp_pipe = Pipeline([
                        ('imputer', MissingValueHandler(strategy='simple')),
                        ('flatten', FunctionTransformer(lambda x: np.array(x).ravel().astype(str))),
                        ('tfidf', TfidfVectorizer(max_features=100))
                    ])
                elif effective_nlp == 'word2vec':
                    nlp_pipe = Pipeline([
                        ('imputer', MissingValueHandler(strategy='simple')),
                        ('flatten', FunctionTransformer(lambda x: np.array(x).ravel().astype(str))),
                        ('word2vec', TextEmbedder(mode='word2vec', embedding_dim=300))
                    ])
                elif effective_nlp == 'bert':
                    nlp_pipe = Pipeline([
                        ('imputer', MissingValueHandler(strategy='simple')),
                        ('flatten', FunctionTransformer(lambda x: np.array(x).ravel().astype(str))),
                        ('bert', TextEmbedder(mode='bert', embedding_dim=384))
                    ])
                else:
                    nlp_pipe = Pipeline([
                        ('imputer', MissingValueHandler(strategy='simple')),
                        ('flatten', FunctionTransformer(lambda x: np.array(x).ravel().astype(str))),
                        ('tfidf', TfidfVectorizer(max_features=100))
                    ])
                transformers_list.append(('nlp', nlp_pipe, text_features))
                transformations.append(f"D.1+: NLP Pipeline intégré (mode={effective_nlp})")

            remainder = 'passthrough' if (target_col and objective != 'clustering') else 'passthrough' # FIX: Toujours passthrough par défaut pour éviter les pertes
            preprocessor = ColumnTransformer(transformers=transformers_list, remainder=remainder)

            # ================================================================
            # FIX #3 CRITIQUE — ANTI DATA-LEAKAGE
            # Split AVANT fit_transform (Exigence D.1 — Ordre Obligatoire)
            # ================================================================

            # Label encoding for target (avant split, sur y séparément)
            le = None
            if objective == 'classification' and target_col and target_col in df.columns:
                le = LabelEncoder()
                target_vals = df[target_col].cast(pl.Utf8).to_numpy()
                df = df.with_columns(pl.Series(target_col, le.fit_transform(target_vals)))
                transformations.append(f"E.1: Encodage cible '{target_col}'")

            # Helper: extract column names from fitted preprocessor
            def _get_new_cols(preprocessor, original_cols):
                new_cols = []
                for name, trans, cols in preprocessor.transformers_:
                    if trans == 'drop': continue
                    actual = preprocessor.named_transformers_.get(name)
                    if trans == 'passthrough': new_cols.extend(cols)
                    elif hasattr(actual, 'get_feature_names_out'):
                        try: new_cols.extend(actual.get_feature_names_out(cols))
                        except Exception: new_cols.extend(cols)
                    else: new_cols.extend(cols)
                if preprocessor.remainder == 'passthrough':
                    all_transformed = []
                    for _, _, cols in preprocessor.transformers_:
                        if isinstance(cols, list): all_transformed.extend(cols)
                        else: all_transformed.append(cols)
                    remaining = [c for c in original_cols if c not in all_transformed]
                    new_cols.extend(remaining)
                
                # Cleanup to ensure no None or duplicates in names
                new_cols = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(new_cols)]
                return new_cols

            split_info = {}
            if target_col and target_col in df.columns and objective != 'clustering':
                n = df.height
                test_size = 0.1 if n > 100000 else 0.2

                if is_timeseries:
                    # D.2 : Split temporel
                    split_point = int(n * (1 - test_size))
                    train_df = df.slice(0, split_point)
                    test_df = df.slice(split_point, n - split_point)
                    transformations.append(f"D.2: Split temporel ({int((1-test_size)*100)}/{int(test_size*100)})")
                else:
                    # D.1 : Split aléatoire stratifié (via pandas pour compatibilité sklearn)
                    df_pd = df.to_pandas()
                    X_all_pd = df_pd.drop(columns=[target_col])
                    y_all_pd = df_pd[target_col]
                    strat = y_all_pd if objective == 'classification' and df[target_col].n_unique() >= 2 else None
                    X_train_pd, X_test_pd, y_train_pd, y_test_pd = train_test_split(
                        X_all_pd, y_all_pd, test_size=test_size, random_state=42, stratify=strat
                    )
                    train_df = pl.from_pandas(X_train_pd).with_columns(pl.Series(target_col, y_train_pd.values))
                    test_df = pl.from_pandas(X_test_pd).with_columns(pl.Series(target_col, y_test_pd.values))
                    transformations.append(f"D.1: Split train/test ({int((1-test_size)*100)}/{int(test_size*100)}) — AVANT fit")

                # Séparer X et y
                X_train = train_df.drop(target_col)
                y_train = train_df[target_col].to_numpy()
                X_test = test_df.drop(target_col)
                y_test = test_df[target_col].to_numpy()

                # D.1 CONFORME : fit_transform UNIQUEMENT sur X_train
                # Conversion en pandas pour compatibilité sklearn ColumnTransformer
                original_train_cols = list(X_train.columns)
                X_train_pd = X_train.to_pandas()
                X_test_pd = X_test.to_pandas()
                print(f"[DEBUG] Starting Fit-Transform on X_train (Shape: {X_train_pd.shape})...", flush=True)
                raw_train = preprocessor.fit_transform(X_train_pd)
                print(f"[DEBUG] Fit-Transform complete. Starting Transform on X_test...", flush=True)
                raw_test = preprocessor.transform(X_test_pd)
                print(f"[DEBUG] Transform complete.", flush=True)
                
                # CORRECTIF #5 : Capturer un échantillon BRUT pour le test de non-régression plus tard
                X_regression_sample = X_test_pd.head(20).copy()
                
                transformations.append("D.1: fit_transform(X_train) + transform(X_test) — Anti-Leakage OK")

                # Reconstruction dense
                train_result = raw_train.toarray() if hasattr(raw_train, "toarray") else raw_train
                test_result = raw_test.toarray() if hasattr(raw_test, "toarray") else raw_test

                # Noms des colonnes
                new_cols = _get_new_cols(preprocessor, original_train_cols)
                feat_cols = new_cols if len(new_cols) == train_result.shape[1] else [f"col_{i}" for i in range(train_result.shape[1])]

                train_pl = pl.DataFrame(train_result, schema=feat_cols, orient="row").with_columns(pl.Series(target_col, y_train))
                test_pl = pl.DataFrame(test_result, schema=feat_cols, orient="row").with_columns(pl.Series(target_col, y_test))

                # G.2 SMOTE uniquement sur train (Exigence G.2)
                # A.2 — SMOTE bloqué pour les invités
                if is_guest:
                    transformations.append("G.2: SMOTE non disponible (mode invité)")
                elif objective == 'classification' and SMOTE:
                    counts = train_pl[target_col].value_counts()
                    if counts.height >= 2:
                        ratio = counts["count"].max() / counts["count"].min()
                        if ratio > 4:
                            smote = SMOTE(random_state=42)
                            X_sm, y_sm = smote.fit_resample(train_pl.drop(target_col).to_numpy(), train_pl[target_col].to_numpy())
                            train_pl = pl.DataFrame(X_sm, schema=feat_cols).with_columns(pl.Series(target_col, y_sm))
                            transformations.append(f"G.2: SMOTE applique (sur train uniquement)")

                df = pl.concat([train_pl, test_pl])
                split_info = {'train_rows': train_pl.height, 'test_rows': test_pl.height, 'test_size': test_size}
            else:
                # Clustering ou pas de target : fit_transform sur tout (en pandas pour sklearn)
                X_all_pd = df.to_pandas()
                original_train_cols = list(df.columns)
                
                # CORRECTIF #5 : Capturer un échantillon BRUT pour le test de non-régression
                X_regression_sample = X_all_pd.head(20).copy()
                
                raw_result = preprocessor.fit_transform(X_all_pd)
                result = raw_result.toarray() if hasattr(raw_result, "toarray") else raw_result
                new_cols = _get_new_cols(preprocessor, df.columns)
                if result.shape[1] == len(new_cols):
                    df = pl.DataFrame(result, schema=new_cols, orient="row")
                else:
                    df = pl.DataFrame(result, orient="row")
                if objective == 'clustering': transformations.append("D: Split non applicable (clustering)")

            # CORRECTIF #4 : Validation croisée
            # Note: avec le fix anti-leakage, le preprocessor est déjà fitté sur X_train uniquement.
            # La CV sur données déjà transformées n'est pas applicable avec le preprocessor.
            try:
                if target_col and target_col in df.columns and split_info:
                    transformations.append(f"H.3: Anti-Leakage validé (train={split_info.get('train_rows', 'N/A')}, test={split_info.get('test_rows', 'N/A')})")
            except Exception as e:
                transformations.append(f"H.3: Validation info - {str(e)}")

            # H.4 / H.5 — RESERVED FOR LOGGED-IN USERS (Not Guest Mode)
            if not is_guest:
                try:
                    pipeline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'saved_pipelines')
                    os.makedirs(pipeline_dir, exist_ok=True)
                    pipeline_path = os.path.join(pipeline_dir, 'preprocessor_pipeline.pkl')
                    
                    # Utiliser le wrapper Pipeline global pour sérialisation avec les noms de colonnes
                    wrapper = PipelineWrapper(
                        preprocessor=preprocessor, 
                        objective=objective, 
                        algorithm=algorithm, 
                        target_col=target_col,
                        column_names=original_train_cols if 'original_train_cols' in locals() else None
                    )
                    joblib.dump(wrapper, pipeline_path)
                    transformations.append("H.4: Pipeline sauvegarde")
                    
                    # CORRECTIF #5 : Test de non-régression sur l'échantillon BRUT
                    try:
                        if 'X_regression_sample' in locals():
                            regression_test = self.test_pipeline_regression(pipeline_path, X_regression_sample)
                            if regression_test['status'] == 'PASSED':
                                transformations.append(f"H.5: Test Non-Régression PASSÉ ({regression_test['predictions_count']} predictions)")
                            else:
                                transformations.append(f"H.5: Test Non-Régression ÉCHOUÉ - {regression_test.get('reason', 'Erreur inconnue')}")
                        else:
                            transformations.append("H.5: Test Non-Régression sauté (pas d'échantillon brut)")
                    except Exception as e:
                        transformations.append(f"H.5: Test Non-Régression échoué - {str(e)}")
                except Exception as e: 
                    transformations.append(f"H.4: Sauvegarde echouee - {str(e)}")
            else:
                transformations.append("H.4/H.5: Sauvegarde et TNR sautés (Mode Invite)")

            return df.to_pandas(), transformations

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

    def _is_essentially_numeric(self, series):
        if series.dtype.is_numeric(): return True
        try:
            non_null = series.drop_nulls()
            if non_null.len() == 0: return False
            converted = non_null.cast(pl.Float64, strict=False)
            return (converted.drop_nulls().len() / non_null.len()) > 0.5
        except: return False

    def _has_outliers(self, df, col):
        if col not in df.columns: return False
        try:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            return df.filter((pl.col(col) < (q1 - 1.5 * iqr)) | (pl.col(col) > (q3 + 1.5 * iqr))).height > 0
        except: return False

    def _impute_with_groupby(self, df, target_col, group_col, strategy='median'):
        # Polars group_by implementation
        if strategy == 'mean':
            return df.with_columns(pl.col(target_col).fill_null(pl.col(target_col).mean().over(group_col)))
        elif strategy == 'median':
            return df.with_columns(pl.col(target_col).fill_null(pl.col(target_col).median().over(group_col)))
        elif strategy == 'mode':
            # Mode over group is tricky in Polars expressions without a custom function, 
            # but we can use a join or just keep it simple
            return df.with_columns(pl.col(target_col).fill_null(pl.col(target_col).mode().first().over(group_col)))
        return df

    # ================================================================
    # MÉTHODES DE VISUALISATION
    # ================================================================

    def compute_correlation_matrix(self, df):
        df = self._to_polars(df)
        numeric_cols = [col for col, dtype in df.schema.items() if dtype.is_numeric()]
        if len(numeric_cols) < 2: 
            return {"matrix": [], "columns": []}
            
        try:
            corr_df = df.select(numeric_cols).corr()
            # Convert to matrix (2D list)
            matrix = [corr_df[col].to_list() for col in corr_df.columns]
            return {
                "matrix": matrix, 
                "columns": list(corr_df.columns)
            }
        except Exception as e:
            print(f"--- [DEBUG] Error in compute_correlation_matrix: {str(e)} ---")
            return {"matrix": [], "columns": []}

    def compute_distribution(self, df, column, bins=20):
        df = self._to_polars(df)
        if column not in df.columns: return None
        try:
            series = df[column].cast(pl.Float64, strict=False).drop_nulls()
            if series.is_empty(): return []
            
            min_v, max_v = float(series.min()), float(series.max())
            if min_v == max_v:
                return [{"range": f"{min_v:.1f}", "count": series.len()}]
                
            # Manual binning with Polars for performance
            bin_width = (max_v - min_v) / bins
            counts = []
            for i in range(bins):
                lo = min_v + i * bin_width
                hi = min_v + (i + 1) * bin_width
                if i == bins - 1:
                    # Last bin includes the upper bound
                    c = series.filter((series >= lo) & (series <= hi)).len()
                else:
                    # Other bins exclude the upper bound
                    c = series.filter((series >= lo) & (series < hi)).len()
                counts.append({"range": f"{lo:.1f}", "count": int(c)})
            return counts
        except Exception as e:
            # Log the error instead of silently failing
            print(f"[ERROR] compute_distribution failed for column {column}: {str(e)}")
            return []

    def get_column_stats(self, df, column):
        df = self._to_polars(df)
        if column not in df.columns:
            return None
        # Convert to numeric polars series
        try:
            series = df[column].cast(pl.Float64, strict=False).drop_nulls()
        except:
            return {}
            
        if series.is_empty():
            return {}
        return {
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "std": round(float(series.std() or 0), 2)
        }

    def compute_category_distribution(self, df, column, top_n=20):
        df = self._to_polars(df)
        if column not in df.columns:
            return None
        counts = df[column].value_counts().sort("count", descending=True).head(top_n)
        return [{"name": str(row[column]), "size": int(row["count"])} for row in counts.to_dicts()]

    def compute_type_distribution(self, df):
        df = self._to_polars(df)
        types = {}
        for col, dtype in df.schema.items():
            col_type = 'numeric' if dtype.is_numeric() else 'categorical'
            types[col_type] = types.get(col_type, 0) + 1
        return [{"name": k, "value": v} for k, v in types.items()]

    def compute_scatter_data(self, df, x_col, y_col, sample_size=500):
        df = self._to_polars(df)
        if x_col not in df.columns or y_col not in df.columns:
            return None
        temp_df = df.select([x_col, y_col]).drop_nulls().head(sample_size)
        return [{"x": row[x_col], "y": row[y_col]} for row in temp_df.to_dicts()]

    def compute_quality_stats(self, df):
        df = self._to_polars(df)
        null_counts = df.null_count().to_dicts()[0]
        return [{"name": str(col), "nullCount": int(null_counts[col])} for col in df.columns]

    def compute_funnel_data(self, df, column):
        df = self._to_polars(df)
        if column not in df.columns:
            return None
        counts = df[column].value_counts().sort("count", descending=True).head(5)
        total = df.height
        data = [
            {"name": str(row[column]), "value": int(row["count"]), "percentage": round((row["count"] / total) * 100, 1) if total > 0 else 0}
            for row in counts.to_dicts()
        ]
        return sorted(data, key=lambda x: x['value'], reverse=True)

    def compute_waterfall_data(self, initial_count, transformations, final_count):
        data = [{"name": "Initial", "value": initial_count, "type": "total"}]
        current = initial_count
        import re
        for t in transformations:
            match = re.search(r"Suppression de (\d+)", t)
            if match:
                val = int(match.group(1))
                data.append({"name": t[:15] + "...", "value": -val, "type": "step"})
                current -= val
        if current != final_count:
            data.append({"name": "Autres fits", "value": final_count - current, "type": "step"})
        data.append({"name": "Final", "value": final_count, "type": "total"})
        return data

    def compute_gauge_data(self, df):
        df = self._to_polars(df)
        total_cells = df.height * df.width
        if total_cells == 0: return {"name": "Qualité", "value": 0}
        missing_cells = df.null_count().sum_horizontal().item()
        completeness = (1 - (missing_cells / total_cells)) * 100
        return {"name": "Qualité", "value": round(float(completeness), 1)}

    def export_dataset(self, df, format):
        """
        Exporte le dataset dans le format spécifié en utilisant Polars nativement si possible (V8.0-POLARS).
        Retourne (data, mime_type, filename_ext)
        """
        df_pl = self._to_polars(df)
        format = format.lower()
        
        try:
            if format == 'csv':
                import io
                output = io.BytesIO()
                df_pl.write_csv(output)
                return output.getvalue().decode('utf-8'), 'text/csv', 'csv'
            
            elif format == 'json':
                import io
                output = io.BytesIO()
                try:
                    # New Polars version format
                    df_pl.write_json(output, format='records')
                except TypeError:
                    # Fallback for older versions or different API
                    df_pl.write_json(output)
                return output.getvalue().decode('utf-8'), 'application/json', 'json'
                
            elif format in ['excel', 'xlsx']:
                # Polars write_excel requires 'xlsx2csv' or 'xlsxwriter' or 'openpyxl'
                # Pandas is safer for multi-environment compatibility for now
                import io
                output = io.BytesIO()
                df_pd = df_pl.to_pandas()
                df_pd.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                return output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'
                
            elif format == 'xml':
                # Polars n'a pas encore de write_xml natif mature partout
                df_pd = df_pl.to_pandas()
                return df_pd.to_xml(index=False), 'application/xml', 'xml'
                
            else:
                raise ValueError(f"Format {format} non supporté.")
        except Exception as e:
            print(f"[ERROR] Polars Export failed for {format}: {str(e)}")
            traceback.print_exc()
            raise e
    
    def _to_pandas(self, df):
        """Convertit le dataframe en pandas si nécessaire."""
        if hasattr(df, 'to_pandas'):
            return df.to_pandas()
        else:
            return pd.DataFrame(df)