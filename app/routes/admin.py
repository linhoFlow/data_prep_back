from flask import Blueprint, jsonify, request
from app.repositories.user_repository import UserRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.events_repository import EventsRepository
from app.middleware.auth_middleware import admin_required
from app.services.email_service import EmailService
from app import db
from bson import ObjectId
import time
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)
user_repo = UserRepository()
email_service = EmailService()

@admin_bp.route('/users', methods=['GET'])
@admin_required()
def list_users():
    users = user_repo.find_all()
    # On renvoie les clients (Tout ce qui n'est pas admin/manager)
    clients = [u for u in users if u.get('role') not in ['admin', 'manager']]
    for user in clients:
        try:
            user['id'] = str(user.pop('_id'))
            user.pop('password', None)
        except (KeyError, AttributeError):
            continue
    return jsonify(clients), 200

@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@admin_required()
def delete_user(user_id):
    """Supprime un client (regular user)"""
    try:
        user = user_repo.find_by_id(user_id)
        if not user:
            return jsonify(msg="Client non trouvé"), 404
            
        # Sécurité : On ne peut pas supprimer un admin/manager via cette route
        if user.get('role') in ['admin', 'manager']:
            return jsonify(msg="Action non autorisée sur ce type de compte"), 403

        success = user_repo.delete(user_id)
        if success:
            return jsonify(msg="Client supprimé avec succès"), 200
        return jsonify(msg="Erreur lors de la suppression en base"), 500
    except Exception as e:
        print(f">>> [ADMIN ERROR] Error deleting user {user_id}: {str(e)}")
        return jsonify(msg=f"Erreur interne lors de la suppression: {str(e)}"), 500

@admin_bp.route('/managers', methods=['GET'])
@admin_required()
def list_managers():
    users = user_repo.find_all()
    # On renvoie uniquement les gestionnaires (role 'manager')
    managers = [u for u in users if u.get('role') == 'manager']
    for user in managers:
        user['id'] = str(user.pop('_id'))
        user.pop('password', None)
    return jsonify(managers), 200

@admin_bp.route('/managers/<user_id>/status', methods=['POST'])
@admin_required()
def toggle_manager_status(user_id):
    try:
        user = user_repo.find_by_id(user_id)
        if not user:
            return jsonify(msg="Gestionnaire non trouvé"), 404
            
        current_status = user.get('is_active', False)
        new_status = not current_status
        
        success = user_repo.update(user_id, {"is_active": new_status})
        if success:
            # Notifier le gestionnaire par email
            email_service.send_manager_status_update(user['email'], new_status)
            return jsonify(msg=f"Compte {'activé' if new_status else 'désactivé'}"), 200
        return jsonify(msg="Erreur lors de la mise à jour"), 500
    except Exception as e:
        print(f">>> [ADMIN ERROR] Error toggling status for {user_id}: {str(e)}")
        return jsonify(msg=f"Erreur interne: {str(e)}"), 500

@admin_bp.route('/managers/<user_id>/role', methods=['POST'])
@admin_required()
def update_manager_role(user_id):
    data = request.get_json()
    new_role = data.get('role')
    
    if new_role not in ['manager', 'admin']:
        return jsonify(msg="Rôle invalide"), 400
        
    success = user_repo.update(user_id, {"role": new_role})
    if success:
        return jsonify(msg=f"Rôle mis à jour vers {new_role}"), 200
    return jsonify(msg="Utilisateur non trouvé"), 404

@admin_bp.route('/managers/<user_id>', methods=['DELETE'])
@admin_required()
def delete_manager(user_id):
    try:
        user = user_repo.find_by_id(user_id)
        if not user:
            return jsonify(msg="Gestionnaire non trouvé"), 404
            
        success = user_repo.delete(user_id)
        if success:
            # Notifier le gestionnaire par email
            email_service.send_manager_deletion_notification(user['email'])
            return jsonify(msg="Compte supprimé avec succès"), 200
        return jsonify(msg="Erreur lors de la suppression"), 500
    except Exception as e:
        print(f">>> [ADMIN ERROR] Error deleting manager {user_id}: {str(e)}")
        return jsonify(msg=f"Erreur interne: {str(e)}"), 500

@admin_bp.route('/stats', methods=['GET'])
@admin_required()
def get_stats():
    start_time = time.time()
    
    # Repositories
    dataset_repo = DatasetRepository()
    session_repo = SessionRepository()
    events_repo = EventsRepository()
    
    users = user_repo.find_all()
    total_users = len(users)
    
    # On considère comme client tout ce qui n'est pas 'admin' ou 'manager'
    all_clients = [u for u in users if u.get('role') not in ['admin', 'manager']]
    clients_count = len(all_clients)
    managers_count = len([u for u in users if u.get('role') == 'manager'])
    
    # 1. Distribution des tiers et Nouveaux clients
    tier_distribution = {}
    new_clients_this_week = 0
    one_week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    for user in all_clients:
        t = user.get('tier', 'starter')
        tier_distribution[t] = tier_distribution.get(t, 0) + 1
        # Compter les nouveaux clients
        if user.get('created_at') and user.get('created_at') >= one_week_ago:
            new_clients_this_week += 1
            
    # Calcul de tendance (simplifié : % de nouveaux utilisateurs ce mois-ci)
    this_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    new_this_month = len([u for u in users if u.get('created_at') and u.get('created_at') >= this_month])
    user_growth_pct = int((new_this_month / total_users * 100)) if total_users > 0 else 0
    user_trend = {"value": f"+{user_growth_pct}% ce mois", "up": True} if user_growth_pct > 0 else {"value": "Stable", "up": True}
    client_trend = {"value": f"{new_clients_this_week} nouveaux", "up": True}
        
    # 2. Santé Système (Ratio sessions réussies / total sessions)
    all_sessions = session_repo.find_all()
    total_sessions = len(all_sessions)
    if total_sessions > 0:
        # On simule un succès si pas explicitement marqué 'failed'
        successful_sessions = len([s for s in all_sessions if s.get('status') != 'failed'])
        system_health = f"{int((successful_sessions / total_sessions) * 100)}%"
    else:
        system_health = "100%"

    # 3. Dernières Activités (Users, Datasets, Sessions)
    recent_activities = []
    
    # Nouveaux utilisateurs
    for u in sorted(users, key=lambda x: x.get('created_at', ''), reverse=True)[:3]:
        is_staff = u.get('role') in ['admin', 'manager']
        recent_activities.append({
            "title": "Nouveau gestionnaire" if is_staff else "Nouvel utilisateur",
            "desc": f"{u['name']} s'est inscrit.",
            "time": _format_time_ago(u.get('created_at')),
            "icon": "Shield" if is_staff else "Users",
            "color": "bg-blue-100 text-blue-600"
        })
        
    # Derniers datasets
    all_datasets = dataset_repo.find_all()
    for d in sorted(all_datasets, key=lambda x: x.get('created_at', ''), reverse=True)[:2]:
        recent_activities.append({
            "title": "Nouveau Dataset",
            "desc": f"Fichier {d['filename']} importé.",
            "time": _format_time_ago(d.get('created_at')),
            "icon": "TrendingUp",
            "color": "bg-navy-50 text-navy-600"
        })
    
    # 4. Derniers Messages (Support)
    recent_messages = []
    chat_history = list(db.chat_history.find().sort("updated_at", -1).limit(3))
    for chat in chat_history:
        # Trouver le nom de l'utilisateur
        user = next((u for u in users if str(u['_id']) == str(chat.get('user_id'))), None)
        user_name = user['name'] if user else "Inconnu"
        recent_messages.append({
            "user": user_name[:2].upper(),
            "name": user_name,
            "msg": chat.get('title', 'Discussion Chatbot'),
            "time": _format_time_ago(chat.get('updated_at'))
        })

    # 5. Événements
    upcoming_events = []
    events = events_repo.find_upcoming(limit=2)
    for ev in events:
        upcoming_events.append({
            "title": ev['title'],
            "date": ev['event_date'],
            "type": ev.get('type', 'maintenance')
        })

    db_latency = f"{int((time.time() - start_time) * 1000)}ms"

    return jsonify({
        "total_users": total_users,
        "clients_count": clients_count,
        "managers_count": managers_count,
        "tier_distribution": tier_distribution,
        "system_health": system_health,
        "db_latency": db_latency,
        "user_trend": user_trend,
        "client_trend": client_trend,
        "recent_activities": sorted(recent_activities, key=lambda x: x['time'])[:4],
        "recent_messages": recent_messages,
        "upcoming_events": upcoming_events,
        "status": "online"
    }), 200

def _format_time_ago(dt_str):
    if not dt_str: return "Récemment"
    try:
        dt = datetime.fromisoformat(dt_str)
        diff = datetime.utcnow() - dt
        if diff.days > 0: return f"{diff.days}j"
        if diff.seconds > 3600: return f"{diff.seconds // 3600}h"
        if diff.seconds > 60: return f"{diff.seconds // 60}m"
        return "Instants"
    except:
        return "Récemment"
