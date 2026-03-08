from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.repositories.session_repository import SessionRepository
from datetime import datetime
from bson import ObjectId

sessions_bp = Blueprint('sessions', __name__)
session_repo = SessionRepository()

@sessions_bp.route('/', methods=['POST'])
@jwt_required()
def create_session():
    """
    Création d'une nouvelle session de preprocessing
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # print(f">>> [SESSION DEBUG] Creating session for user_id: {user_id}", flush=True)

        session_data = {
            "user_id": user_id,
            "name": data.get('name', 'Nouvelle Session'),
            "filename": data.get('filename'),
            "dataset_id": data.get('dataset_id'),
            "rowCount": data.get('rowCount', 0),
            "columnCount": data.get('columnCount', 0),
            "pipeline": data.get('pipeline', []),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        session_id = session_repo.create(session_data)
        return jsonify({"id": session_id, "message": "Session sauvegardée"}), 201
    except Exception as e:
        print(f">>> [SESSION ERROR] {str(e)}", flush=True)
        return jsonify({"message": str(e)}), 500

@sessions_bp.route('/', methods=['GET'])
@jwt_required()
def get_user_sessions():
    user_id = get_jwt_identity()
    sessions = session_repo.find_by_user(user_id)
    # Convert ObjectIds to strings for JSON
    for s in sessions:
        s['id'] = str(s.pop('_id'))
    return jsonify(sessions), 200

@sessions_bp.route('/<session_id>', methods=['GET'])
@jwt_required()
def get_session(session_id):
    user_id = get_jwt_identity()
    session = session_repo.find_by_id(session_id)
    if not session or session['user_id'] != user_id:
        return jsonify({"message": "Session non trouvée"}), 404
    
    session['id'] = str(session.pop('_id'))
    return jsonify(session), 200

@sessions_bp.route('/<session_id>', methods=['PUT'])
@jwt_required()
def update_session(session_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    data['updated_at'] = datetime.utcnow()
    
    session_repo.update_session(session_id, user_id, data)
    return jsonify({"message": "Session mise à jour"}), 200

@sessions_bp.route('/<session_id>', methods=['DELETE'])
@jwt_required()
def delete_session(session_id):
    user_id = get_jwt_identity()
    # verify ownership before delete
    session = session_repo.find_by_id(session_id)
    if session and session['user_id'] == user_id:
        session_repo.delete(session_id)
        return jsonify({"message": "Session supprimée"}), 200
    return jsonify({"message": "Non autorisé"}), 403
