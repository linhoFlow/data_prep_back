# -*- coding: utf-8 -*-
"""
Configuration centralisée des limites par niveau d'utilisateur.
"""

TIER_HIERARCHY = ["guest", "starter", "enterprise"]

TIER_LIMITS = {
    "guest": {
        "max_file_size_mb": 5,
        "max_columns": 20,
        "max_rows": 1000,
        "max_files": 1,
        "max_operations_per_hour": 3,
        "session_timeout_minutes": 30,
        "allowed_imputation": ["mean", "median", "mode"],
        "allowed_encoding": ["ohe", "ordinal", "label"],
        "allowed_export_formats": ["csv"],
        "allowed_algorithms": ["rf"],
        "allowed_nlp": [],
        "blocked_features": [
            "nlp_tfidf", "nlp_word2vec", "nlp_bert",
            "knn_imputer", "iterative_imputer",
            "smote", "isolation_forest", "lof", "elliptic_envelope",
            "nn", "neural_network",
            "pipeline_export_pkl", "save_pipeline", "regression_test",
            "advanced_visuals", "autopilot", "autopilot_full",
            "scatter_matrix", "correlation_heatmap", "funnel_chart",
        ],
        "report_visible_percent": 30,
    },

    "starter": {
        "max_file_size_mb": None,
        "max_columns": None,
        "max_rows": None,
        "max_files": None,
        "max_operations_per_hour": None,
        "session_timeout_minutes": None,
        "allowed_imputation": None,
        "allowed_encoding": None,
        "allowed_export_formats": ["csv", "xlsx", "json", "xml", "pkl"],
        "allowed_algorithms": None,
        "allowed_nlp": ["tfidf", "word2vec", "bert"],
        "blocked_features": [],
        "report_visible_percent": 100,
    },

    "enterprise": {
        "max_file_size_mb": None,
        "max_columns": None,
        "max_rows": None,
        "max_files": None,
        "max_operations_per_hour": None,
        "session_timeout_minutes": None,
        "allowed_imputation": None,
        "allowed_encoding": None,
        "allowed_export_formats": ["csv", "xlsx", "json", "xml", "pkl"],
        "allowed_algorithms": None,
        "allowed_nlp": ["tfidf", "word2vec", "bert"],
        "blocked_features": [],
        "report_visible_percent": 100,
    },
}

def get_tier_limits(tier: str) -> dict:
    return TIER_LIMITS.get(tier, TIER_LIMITS["guest"])

def is_feature_blocked(tier: str, feature: str) -> bool:
    limits = get_tier_limits(tier)
    return feature in limits.get("blocked_features", [])

def check_data_limits(tier: str, file_size_mb: float = 0, n_cols: int = 0, n_rows: int = 0) -> dict:
    limits = get_tier_limits(tier)
    if limits["max_file_size_mb"] is not None and file_size_mb > limits["max_file_size_mb"]:
        return {
            "allowed": False, 
            "reason": "Fichier trop volumineux", 
            "trigger": "file_size",
            "upgrade_hint": f"Votre fichier fait {file_size_mb:.1f} MB. La limite pour le niveau '{tier}' est de {limits['max_file_size_mb']} MB. Veuillez mettre à niveau votre abonnement."
        }
    if limits["max_columns"] is not None and n_cols > limits["max_columns"]:
        return {
            "allowed": False, 
            "reason": "Trop de colonnes", 
            "trigger": "columns",
            "upgrade_hint": f"Votre fichier a {n_cols} colonnes. La limite pour le niveau '{tier}' est de {limits['max_columns']} colonnes. Veuillez mettre à niveau votre abonnement."
        }
    if limits["max_rows"] is not None and n_rows > limits["max_rows"]:
        return {
            "allowed": False, 
            "reason": "Trop de lignes", 
            "trigger": "rows",
            "upgrade_hint": f"Votre fichier a {n_rows:,} lignes. La limite pour le niveau '{tier}' est de {limits['max_rows']:,} lignes. Veuillez mettre à niveau votre compte."
        }
    return {"allowed": True}

def is_export_format_allowed(tier: str, fmt: str) -> bool:
    """Vérifie si un format d'export spécifique est autorisé pour le tier donné."""
    limits = get_tier_limits(tier)
    allowed_formats = limits.get("allowed_export_formats", ["csv"])
    return fmt.lower() in [f.lower() for f in allowed_formats]

def is_algorithm_allowed(tier: str, algorithm: str) -> bool:
    """Vérifie si un algorithme spécifique est autorisé pour le tier donné."""
    limits = get_tier_limits(tier)
    allowed_algos = limits.get("allowed_algorithms")
    
    # Si None, tous les algorithmes sont autorisés (Pro/Enterprise)
    if allowed_algos is None:
        return True
    
    # Sinon, vérifier si l'algorithme est dans la liste
    return algorithm.lower() in [a.lower() for a in allowed_algos]

def is_nlp_allowed(tier: str, nlp_type: str) -> bool:
    """Vérifie si un type de NLP spécifique est autorisé pour le tier donné."""
    limits = get_tier_limits(tier)
    allowed_nlp = limits.get("allowed_nlp", [])
    
    # Si liste vide, aucun NLP autorisé
    if not allowed_nlp:
        return False
    
    # Sinon, vérifier si le type de NLP est dans la liste
    return nlp_type.lower() in [n.lower() for n in allowed_nlp]

def get_tier_info(tier: str) -> dict:
    limits = get_tier_limits(tier)
    return {
        "tier": tier,
        "limits": limits,
        "blocked_features": limits.get("blocked_features", []),
    }
