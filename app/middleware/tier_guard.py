# -*- coding: utf-8 -*-
"""
Middleware de validation des tiers.
Décorateurs Flask pour vérifier les permissions utilisateur
basées sur le JWT et le tier_config.
"""
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request, get_jwt_identity
from app.config.tier_config import (
    get_tier_limits, is_feature_blocked, check_data_limits,
    TIER_HIERARCHY, get_tier_info
)
import time

# Rate limiting en mémoire (simple, suffisant pour un serveur unique)
_rate_limit_store = {}  # { "ip_or_token": { "count": int, "reset_at": float } }


def _get_user_info():
    """Extrait le tier, le rôle et l'ID utilisateur du JWT. Défaut tier=guest, role=user."""
    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        if claims:
            tier = claims.get("tier", "guest")
            role = claims.get("role", "user")
            user_id = get_jwt_identity()
            # Si identity est 'guest', c'est un invité
            if user_id == 'guest': user_id = None
            return tier, role, user_id
    except Exception:
        pass
    return "guest", "guest", None

def _get_current_user_id():
    """Helper pour récupérer uniquement l'ID utilisateur."""
    _, _, user_id = _get_user_info()
    return user_id

def _get_user_tier():
    """Backward compatibility shim."""
    tier, _, _ = _get_user_info()
    return tier


def _get_rate_key():
    """Génère une clé unique pour le rate limiting."""
    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        if claims and claims.get("sub"):
            return f"user_{claims['sub']}"
    except Exception:
        pass
    return f"ip_{request.remote_addr}"


def _check_rate_limit(tier: str) -> dict:
    """Vérifie le rate limiting pour le tier donné."""
    limits = get_tier_limits(tier)
    max_ops = limits.get("max_operations_per_hour")
    if max_ops is None:
        return {"allowed": True}

    key = _get_rate_key()
    now = time.time()

    if key not in _rate_limit_store or now > _rate_limit_store[key]["reset_at"]:
        _rate_limit_store[key] = {"count": 0, "reset_at": now + 3600}

    entry = _rate_limit_store[key]
    if entry["count"] >= max_ops:
        remaining = int(entry["reset_at"] - now)
        return {
            "allowed": False,
            "reason": f"Limite atteinte : {max_ops} opérations par heure en mode invité.",
            "upgrade_hint": "Créez un compte pour continuer sans restriction.",
            "retry_after_seconds": remaining,
            "trigger": "rate_limit"
        }

    entry["count"] += 1
    return {"allowed": True, "remaining": max_ops - entry["count"]}


def require_tier(min_tier="starter", feature=None):
    """
    Décorateur qui vérifie le tier minimum de l'utilisateur.
    
    Usage:
        @require_tier("starter", feature="knn_imputer")
        def my_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tier, role = _get_user_info()

            # --- BYPASS ROLE-BASED (Staff : Admin & Manager) ---
            # Les restrictions de tiers ne s'appliquent qu'aux CLUBS / CLIENTS (rôle 'user' ou 'guest')
            if role in ['admin', 'manager']:
                kwargs['_user_tier'] = tier
                return f(*args, **kwargs)

            # Vérifier le tier minimum (pour les clients)
            tier_idx = TIER_HIERARCHY.index(tier) if tier in TIER_HIERARCHY else 0
            min_idx = TIER_HIERARCHY.index(min_tier) if min_tier in TIER_HIERARCHY else 1

            if tier_idx < min_idx:
                return jsonify({
                    "error": "Accès refusé",
                    "reason": f"Cette fonctionnalité nécessite un compte {min_tier}.",
                    "upgrade_hint": f"Passez au niveau {min_tier} pour débloquer cette fonctionnalité.",
                    "current_tier": tier,
                    "required_tier": min_tier,
                    "trigger": "tier_required"
                }), 403

            # Vérifier la feature spécifique (pour les clients)
            if feature and is_feature_blocked(tier, feature):
                return jsonify({
                    "error": "Fonctionnalité bloquée",
                    "reason": f"La fonctionnalité '{feature}' n'est pas disponible pour le niveau {tier}.",
                    "upgrade_hint": _get_feature_upgrade_hint(feature),
                    "current_tier": tier,
                    "blocked_feature": feature,
                    "trigger": "feature_blocked"
                }), 403

            # Injecter le tier dans les kwargs
            kwargs['_user_tier'] = tier
            return f(*args, **kwargs)
        return wrapper
    return decorator


def check_upload_limits(f):
    """
    Décorateur pour vérifier les limites d'upload (taille, colonnes, lignes).
    S'applique APRÈS le parsing du fichier.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        tier, role = _get_user_info()
        kwargs['_user_tier'] = tier
        return f(*args, **kwargs)
    return wrapper


def check_rate_limit_decorator(f):
    """Décorateur pour le rate limiting."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        tier, role = _get_user_info()
        
        # Bypass pour le staff
        if role in ['admin', 'manager']:
            return f(*args, **kwargs)
            
        check = _check_rate_limit(tier)
        if not check["allowed"]:
            return jsonify({
                "error": "Limite de requêtes atteinte",
                **check,
            }), 429
        return f(*args, **kwargs)
    return wrapper


def _get_feature_upgrade_hint(feature: str) -> str:
    """Messages contextuels de conversion par feature (Section C)."""
    hints = {
        "knn_imputer": "Le KNNImputer est disponible uniquement pour les membres. Votre analyse sera plus précise avec cette méthode.",
        "iterative_imputer": "L'IterativeImputer permet une imputation itérative avancée. Créez un compte pour y accéder.",
        "smote": "Le rééquilibrage SMOTE est réservé aux comptes enregistrés.",
        "isolation_forest": "La détection d'outliers par Isolation Forest est une fonctionnalité premium.",
        "lof": "Le Local Outlier Factor (LOF) est disponible avec un compte gratuit.",
        "nlp_tfidf": "Le traitement NLP est disponible pour tous les membres.",
        "nlp_bert": "Les embeddings BERT sont disponibles avec un compte Starter.",
        "nlp_word2vec": "Word2Vec est disponible avec un compte Starter.",
        "advanced_visuals": "Les visualisations avancées (corrélations, scatter matrix) sont réservées aux membres.",
        "pipeline_export_pkl": "L'export du pipeline sklearn (.pkl) est disponible avec un compte Starter.",
        "save_pipeline": "Sauvegardez votre pipeline pour ne jamais recommencer depuis zéro.",
        "regression_test": "Le test de non-régression garantit la reproductibilité de vos résultats.",
        "autopilot_full": "L'Auto-Pilot complet avec toutes les optimisations est réservé aux membres.",
    }
    return hints.get(feature, f"Cette fonctionnalité est réservée aux membres enregistrés.")
