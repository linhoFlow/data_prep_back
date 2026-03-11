import os
import io
import pandas as pd
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import traceback
import json
import uuid

# Importer les services
from app.services.data_processing_service import DataProcessingService
from app.repositories.dataset_repository import DatasetRepository
from datetime import datetime
# from app.services.visualization_service import VisualizationService

# Importer le système de tiers
from app.config.tier_config import (
    get_tier_limits, is_feature_blocked, check_data_limits, get_tier_info
)
from app.middleware.tier_guard import (
    _get_user_tier, check_rate_limit_decorator, require_tier, _check_rate_limit,
    _get_current_user_id
)

datasets_bp = Blueprint('datasets', __name__)
data_service = DataProcessingService()
dataset_repo = DatasetRepository()
# viz_service = VisualizationService()

# -------------------------------------------------------------------
# FIX: Remplacement de "active_datasets" en mémoire par un stockage sur disque.
# Le serveur de dev Flask redémarre lors de l'upload de fichiers, 
# ce qui efface la RAM. Stocker sur disque évite les erreurs 404.
# -------------------------------------------------------------------
DATASETS_STORE_DIR = "/tmp/datasets"
os.makedirs(DATASETS_STORE_DIR, exist_ok=True)

def save_dataset(dataset_id, df):
    """Sauvegarde le dataframe en pickle pour préserver les types de données."""
    filepath = os.path.join(DATASETS_STORE_DIR, f"{dataset_id}.pkl")
    if hasattr(df, 'to_pandas'):
        df.to_pandas().to_pickle(filepath)
    elif isinstance(df, pd.DataFrame):
        df.to_pickle(filepath)
    else:
        # Fallback
        pd.DataFrame(df).to_pickle(filepath)

def load_dataset(dataset_id):
    """Charge le dataframe depuis le pickle."""
    filepath = os.path.join(DATASETS_STORE_DIR, f"{dataset_id}.pkl")
    if os.path.exists(filepath):
        return pd.read_pickle(filepath)
    return None

# ==========================================
# ROUTES TEMPORATOIRES (DEBUG)
# ==========================================
@datasets_bp.route('/ping', methods=['GET'])
def ping():
    import time
    return jsonify({"message": "Pong", "time": time.time()})

# ==========================================
# 1. UPLOAD DE FICHIER
# ==========================================
@datasets_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Route pour uploader un fichier (CSV, Excel).
    Retourne des métadonnées basiques et un ID de session.
    Applique les limites de taille/colonnes/lignes selon le tier.
    """
    print("--- [UPLOAD] Requête reçue ---")
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier fourni dans la requête."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nom de fichier vide."}), 400

    # ── Vérification du tier ──
    tier = _get_user_tier()
    dataset_id = request.form.get('id', str(uuid.uuid4()))

    try:
        filename = secure_filename(file.filename)
        file_content = file.read()
        
        # A.1 — Vérifier la taille du fichier
        file_size_mb = len(file_content) / (1024 * 1024)
        limits = get_tier_limits(tier)
        if limits["max_file_size_mb"] is not None and file_size_mb > limits["max_file_size_mb"]:
            return jsonify({
                "error": "Fichier trop volumineux",
                "reason": f"Votre fichier fait {file_size_mb:.1f} MB. Limite en mode {tier} : {limits['max_file_size_mb']} MB.",
                "upgrade_hint": "Créez un compte Starter pour traiter des fichiers de taille illimitée.",
                "trigger": "file_size",
                "current_tier": tier
            }), 403
        
        # Parser le fichier
        df, error_msg = data_service.parse_file(file_content, filename)
        
        if error_msg:
             return jsonify({"error": error_msg}), 400

        # A.1 — Vérifier les limites colonnes/lignes
        n_rows, n_cols = len(df), len(df.columns) if hasattr(df, 'columns') else 0
        data_check = check_data_limits(tier, file_size_mb, n_cols, n_rows)
        if not data_check["allowed"]:
            return jsonify({
                "error": "Limites de données dépassées",
                **data_check,
                "current_tier": tier
            }), 403

        # ✅ Sauvegarde persistante
        save_dataset(dataset_id, df)
        
        # ✅ Enregistrement dans MongoDB pour le tracking dashboard
        user_id = _get_current_user_id()
        dataset_repo.create({
            "dataset_id": dataset_id,
            "user_id": user_id,
            "filename": filename,
            "size_mb": file_size_mb,
            "rows": n_rows,
            "cols": n_cols,
            "created_at": datetime.utcnow().isoformat()
        })
        
        # Obtenir les informations détaillées pour le frontend
        dataset_info = data_service.get_dataset_info(df, dataset_id)

        print(f"--- [UPLOAD] Succès pour {filename}, ID: {dataset_id}, tier: {tier} ---")

        response_data = {
            "message": "Fichier uploadé et parsé avec succès",
            "filename": filename,
            "tier_info": get_tier_info(tier)
        }
        response_data.update(dataset_info)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"--- [ERREUR UPLOAD] {str(e)} ---")
        trace_str = traceback.format_exc()
        print(trace_str)
        return jsonify({
            "error": "Erreur lors du traitement du fichier",
            "details": str(e),
            "trace": trace_str
        }), 500


# ==========================================
# 2. VUE D'ENSEMBLE (OVERVIEW)
# ==========================================
@datasets_bp.route('/<dataset_id>', methods=['GET'])
def get_dataset(dataset_id):
    """
    Récupère les informations d'un dataset existant par son ID.
    """
    try:
        df = load_dataset(dataset_id)
        if df is None:
            return jsonify({"error": f"Dataset {dataset_id} non trouvé."}), 404
        
        dataset_info = data_service.get_dataset_info(df, dataset_id)
        return jsonify(dataset_info), 200
    except Exception as e:
        print(f"--- [ERREUR GET DATASET] {str(e)}")
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/overview', methods=['GET'])
def get_overview(dataset_id):
    """
    Renvoie les statistiques détaillées pour l'onglet 'Overview'.
    """
    try:
        df = load_dataset(dataset_id)
        if df is None:
            return jsonify({"message": f"Dataset {dataset_id} non trouvé."}), 404
            
        stats = data_service.generate_detailed_stats(df)
        
        return jsonify({
            "dataset_id": dataset_id,
            "stats": stats
        }), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==========================================
# 3. AUTO-PILOT (PRÉTRAITEMENT AUTOMATIQUE)
# ==========================================
@datasets_bp.route('/<dataset_id>/autopilot', methods=['POST'])
def autopilot(dataset_id):
    """
    Applique le pipeline de traitement de données automatique sur le dataset spécifié.
    Applique les restrictions de tier sur les fonctionnalités avancées.
    """
    print(f"--- [AUTOPILOT] Démarrage... ID demandé: {dataset_id} ---", flush=True)
    try:
        # ── Vérification du tier ──
        tier = _get_user_tier()
        is_guest = (tier == "guest")

        # F.3 — Rate limiting pour les invités
        rate_check = _check_rate_limit(tier)
        if not rate_check["allowed"]:
            return jsonify({
                "error": "Limite de requêtes atteinte",
                **rate_check,
                "current_tier": tier
            }), 429

        data = request.json or {}
        objective = data.get('objective', 'classification')
        algorithm = data.get('algorithm')
        nlp_mode = data.get('nlp')

        # A.2 — Bloquer NLP pour les invités
        if nlp_mode and nlp_mode != 'none':
            feature_key = f"nlp_{nlp_mode}"
            if is_feature_blocked(tier, feature_key):
                return jsonify({
                    "error": "Fonctionnalité bloquée",
                    "reason": f"Le traitement NLP ({nlp_mode}) n'est pas disponible en mode {tier}.",
                    "upgrade_hint": "Le NLP est disponible avec un compte Pro.",
                    "trigger": "feature_blocked",
                    "blocked_feature": feature_key,
                    "current_tier": tier
                }), 403

        # A.2 — Bloquer l'Auto-Pilot complet pour les invités
        if is_guest and is_feature_blocked(tier, "autopilot_full"):
            # Mode invité : autopilot simplifié (imputation simple, pas de LOF/SMOTE)
            pass  # Le flag is_guest sera passé à auto_pilot pour limiter les features

        df = load_dataset(dataset_id)
        if df is None:
            available_files = os.listdir(DATASETS_STORE_DIR) if os.path.exists(DATASETS_STORE_DIR) else []
            print(f"--- [WARNING] Autopilot request for unknown ID: {dataset_id} ---", flush=True)
            return jsonify({
                "message": f"Dataset {dataset_id} non trouvé sur le disque.",
                "debug_info": {
                    "requested_id": dataset_id,
                    "available_files": available_files
                }
            }), 404
        
        df, transforms = data_service.auto_pilot(
            df, 
            objective=objective, 
            algorithm=algorithm, 
            nlp_mode=nlp_mode,
            is_guest=is_guest
        )
        
        # ✅ Sauvegarde persistante du résultat
        save_dataset(dataset_id, df)
        
        # Obtenir les informations détaillées pour le frontend (Dashboard)
        dataset_info = data_service.get_dataset_info(df, dataset_id)

        response_data = {
            "message": "Auto-Pilot appliqué avec succès.",
            "transformations": transforms,
            "tier_info": get_tier_info(tier)
        }
        response_data.update(dataset_info)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"--- [ERREUR AUTOPILOT] ---")
        traceback.print_exc()
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@datasets_bp.route('/<dataset_id>/process', methods=['POST'])
def process_data(dataset_id):
    """
    Applique une transformation manuelle spécifique sur le dataset.
    """
    print(f"--- [PROCESS] ID: {dataset_id} ---", flush=True)
    try:
        data = request.json
        transform_type = data.get('type')
        params = data.get('params', {})

        df = load_dataset(dataset_id)
        if df is None:
            return jsonify({"message": "Dataset non trouvé"}), 404

        # Appliquer la transformation via le service
        df = data_service.apply_transformation(df, transform_type, params)

        # ✅ Sauvegarde persistante
        save_dataset(dataset_id, df)

        # Retourner les infos mises à jour
        dataset_info = data_service.get_dataset_info(df, dataset_id)
        
        return jsonify({
            "message": f"Transformation {transform_type} appliquée",
            **dataset_info
        }), 200

    except Exception as e:
        print(f"--- [ERREUR PROCESS] {str(e)} ---")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==========================================
# 4. EXPORT DES DONNÉES PRÉTRAITÉES
# ==========================================
@datasets_bp.route('/<dataset_id>/export', methods=['GET'])
def export_data(dataset_id):
    """
    Exporte le dataset dans différents formats (csv, json, excel, xml).
    Applique les restrictions de format selon le tier + filigrane pour les invités.
    """
    fmt = request.args.get('format', 'csv').lower().strip()
    tier = _get_user_tier()
    
    filename_suggestion = request.args.get('filename', 'donnees_pretraitees').strip()
    print(f"[DEBUG] Export request - Dataset: {dataset_id}, Format: {fmt}, Tier: {tier}, Suggestion: {filename_suggestion}")
    
    try:
        # Vérifier le format autorisé pour ce tier
        limits = get_tier_limits(tier)
        allowed_formats = limits.get("allowed_export_formats", ["csv"])
        print(f"[DEBUG] Allowed formats for {tier}: {allowed_formats}")
        
        if fmt not in allowed_formats:
            print(f"[DEBUG] Format {fmt} BLOCKED for tier {tier}")
            return jsonify({
                "error": "Format d'export non autorisé",
                "reason": f"Le format '{fmt}' n'est pas disponible en mode {tier}.",
                "allowed_formats": allowed_formats,
                "upgrade_hint": "Exportez en Excel, JSON et XML sans restrictions avec un compte Starter.",
                "trigger": "export_format",
                "current_tier": tier
            }), 403

        df = load_dataset(dataset_id)
        if df is None:
            return jsonify({"message": "Dataset non trouvé"}), 404

        # D.3 — Filigrane pour les invités (CSV uniquement)
        if tier == "guest" and fmt == "csv":
            print(f"[DEBUG] Applying guest watermark for CSV")
            buf = io.StringIO()
            buf.write("# Généré par DataPrep Pro — Mode Invité\n")
            buf.write("# Créez un compte gratuit pour débloquer toutes les fonctionnalités\n")
            df.to_csv(buf, index=False)
            data = buf.getvalue()
            mime_type = 'text/csv'
            ext = 'csv'
            clean_filename = f"{filename_suggestion}.csv"
        else:
            print(f"[DEBUG] Exporting full dataset via data_service for tier {tier}")
            data, mime_type, ext = data_service.export_dataset(df, fmt)
            clean_filename = f'{filename_suggestion}.{ext}'
        
        print(f"[DEBUG] Sending file: {clean_filename}, MIME: {mime_type}")
        
        # Transformation en bytes si nécessaire
        file_obj = io.BytesIO(data.encode('utf-8') if isinstance(data, str) else data)
        
        from flask import send_file
        from urllib.parse import quote
        
        # RFC 6266
        disposition = f'attachment; filename="{clean_filename}"; filename*=UTF-8\'\'{quote(clean_filename)}'
        
        print(f"[DEBUG] Export Final - Filename: {clean_filename}")
        
        response = send_file(
            file_obj,
            mimetype=mime_type,
            as_attachment=True,
            download_name=clean_filename,
            conditional=False
        )
        
        # Force headers on the send_file response
        response.headers["Content-Disposition"] = disposition
        response.headers["X-Suggested-Filename"] = clean_filename
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition, Content-Type, X-Suggested-Filename"
        
        # Prevent caching of UUID streams
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
            
    except Exception as e:
        print(f">>> [EXPORT ERROR] {str(e)}")
        traceback.print_exc()
        return jsonify({
            "error": "Échec de l'exportation",
            "message": str(e),
            "trigger": "export_error"
        }), 500
# ==========================================
# 5. VISUALISATIONS (DASHBOARD)
# ==========================================

@datasets_bp.route('/<dataset_id>/types', methods=['GET'])
def get_types(dataset_id):
    try:
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_type_distribution(df))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/quality', methods=['GET'])
def get_quality(dataset_id):
    try:
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_quality_stats(df))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/correlation', methods=['GET'])
def get_correlation(dataset_id):
    try:
        tier = _get_user_tier()
        if is_feature_blocked(tier, "correlation_heatmap"):
            return jsonify({
                "locked": True,
                "reason": "Les visualisations avancées sont réservées aux membres.",
                "upgrade_hint": "Créez un compte gratuit pour débloquer la matrice de corrélation.",
                "trigger": "advanced_visuals",
                "current_tier": tier
            }), 200
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_correlation_matrix(df))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/stats', methods=['GET'])
def get_stats(dataset_id):
    try:
        column = request.args.get('column')
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.get_column_stats(df, column))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/distribution', methods=['GET'])
def get_distribution(dataset_id):
    try:
        column = request.args.get('column')
        bins = int(request.args.get('bins', 20))
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_distribution(df, column, bins))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/categories', methods=['GET'])
def get_categories(dataset_id):
    try:
        column = request.args.get('column')
        top_n = int(request.args.get('top_n', 20))
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_category_distribution(df, column, top_n))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/scatter', methods=['GET'])
def get_scatter(dataset_id):
    try:
        tier = _get_user_tier()
        if is_feature_blocked(tier, "scatter_matrix"):
            return jsonify({
                "locked": True,
                "reason": "La scatter matrix est réservée aux membres.",
                "upgrade_hint": "Créez un compte pour visualiser les relations entre variables.",
                "trigger": "advanced_visuals",
                "current_tier": tier
            }), 200
        x = request.args.get('x')
        y = request.args.get('y')
        sample = int(request.args.get('sample', 500))
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_scatter_data(df, x, y, sample))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/funnel', methods=['GET'])
def get_funnel(dataset_id):
    try:
        tier = _get_user_tier()
        if is_feature_blocked(tier, "funnel_chart"):
            return jsonify({
                "locked": True,
                "reason": "Le graphique funnel est réservé aux membres.",
                "upgrade_hint": "Créez un compte pour accéder aux visualisations avancées.",
                "trigger": "advanced_visuals",
                "current_tier": tier
            }), 200
        column = request.args.get('column')
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_funnel_data(df, column))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/waterfall', methods=['GET'])
def get_waterfall(dataset_id):
    try:
        initial = int(request.args.get('initial', 0))
        transforms_str = request.args.get('transforms', '[]')
        transforms = json.loads(transforms_str)
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_waterfall_data(initial, transforms, len(df)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@datasets_bp.route('/<dataset_id>/gauge', methods=['GET'])
def get_gauge(dataset_id):
    try:
        df = load_dataset(dataset_id)
        if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
        return jsonify(data_service.compute_gauge_data(df))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
#         return jsonify(viz_service.generate_boxplots_chart(df))
#     except Exception as e:
#          return jsonify({"error": str(e)}), 500
# 
# @datasets_bp.route('/<dataset_id>/visualizations/gauge', methods=['GET'])
# def get_gauge_viz(dataset_id):
#     try:
#         df = load_dataset(dataset_id)
#         if df is None: return jsonify({"message": "Dataset non trouvé"}), 404
#         return jsonify(viz_service.generate_gauge_chart(df))
#     except Exception as e:
#          return jsonify({"error": str(e)}), 500

