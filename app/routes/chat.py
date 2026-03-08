# -*- coding: utf-8 -*-
"""
Routes pour le chatbot DataBot.
- POST /message : Envoie une question et reçoit une réponse
- GET /history : Historique des conversations (auth requise)
- DELETE /history/<id> : Supprimer une conversation
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app.services.chatbot_service import find_answer
from datetime import datetime
import uuid

chat_bp = Blueprint('chat', __name__)


from app.middleware.tier_guard import _get_current_user_id


@chat_bp.route('/message', methods=['POST'])
def send_message():
    """
    Envoie une question au chatbot et reçoit une réponse.
    Sauvegarde la conversation pour les utilisateurs connectés.
    """
    data = request.get_json()
    question = data.get('message', '').strip()

    if not question:
        return jsonify({"error": "Message vide"}), 400

    # Trouver la réponse
    answer = find_answer(question)

    # Sauvegarder dans l'historique pour les utilisateurs connectés
    user_id = _get_current_user_id()
    conversation_id = data.get('conversation_id')

    if user_id:
        from app import db
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Ajouter les messages à la conversation
        db.chat_history.update_one(
            {"conversation_id": conversation_id, "user_id": user_id},
            {
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "title": question[:50] + ("..." if len(question) > 50 else ""),
                },
                "$push": {
                    "messages": {
                        "$each": [
                            {"role": "user", "content": question, "timestamp": datetime.utcnow().isoformat()},
                            {"role": "bot", "content": answer, "timestamp": datetime.utcnow().isoformat()},
                        ]
                    }
                },
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            },
            upsert=True
        )

    return jsonify({
        "answer": answer,
        "conversation_id": conversation_id if user_id else None,
    })


@chat_bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    """Retourne l'historique des conversations de l'utilisateur."""
    user_id = get_jwt_identity()
    if not user_id or user_id == 'guest':
        return jsonify([])

    from app import db
    conversations = list(
        db.chat_history.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("updated_at", -1).limit(50)
    )
    return jsonify(conversations)


@chat_bp.route('/history/<conversation_id>', methods=['DELETE'])
@jwt_required()
def delete_conversation(conversation_id):
    """Supprime une conversation spécifique."""
    user_id = get_jwt_identity()
    from app import db
    result = db.chat_history.delete_one({
        "conversation_id": conversation_id,
        "user_id": user_id
    })
    if result.deleted_count == 0:
        return jsonify({"message": "Conversation non trouvée"}), 404
    return jsonify({"message": "Conversation supprimée"})
