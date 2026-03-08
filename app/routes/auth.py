from flask import Blueprint, request, jsonify
from app.services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Inscription d'un nouvel utilisateur
    ---
    tags:
      - Authentification
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            email:
              type: string
            password:
              type: string
    responses:
      201:
        description: Utilisateur créé avec succès
      400:
        description: Erreur lors de l'inscription
    """
    data = request.get_json()
    user_id, error = auth_service.register_user(
        data.get('name'), 
        data.get('email'), 
        data.get('password'),
        data.get('role', 'user')
    )
    if error:
        return jsonify({"message": error}), 400
    return jsonify({"id": user_id, "message": "Compte créé"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Connexion utilisateur
    ---
    tags:
      - Authentification
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
            password:
              type: string
    responses:
      200:
        description: Connexion réussie
      401:
        description: Identifiants incorrects
    """
    data = request.get_json()
    result, error = auth_service.login_user(data.get('email'), data.get('password'))
    if error:
        return jsonify({"message": error}), 401
    return jsonify(result), 200

@auth_bp.route('/guest', methods=['POST'])
def guest_login():
    """
    Connexion en mode invité
    """
    result, error = auth_service.guest_login()
    return jsonify(result), 200

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        email = data.get('email')
        success, error = auth_service.forgot_password(email)
        if not success:
            return jsonify({"message": error}), 400
        return jsonify({"message": "Code envoyé par email"}), 200
    except Exception as e:
        print(f">>> [AUTH ERROR] Forgot Password: {str(e)}")
        return jsonify({"message": "Une erreur interne est survenue"}), 500

@auth_bp.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    success, error = auth_service.verify_reset_code(email, code)
    if not success:
        return jsonify({"message": error}), 400
    return jsonify({"message": "Code valide"}), 200

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('password')
    confirm_password = data.get('confirm_password')
    
    if new_password != confirm_password:
        return jsonify({"message": "Les mots de passe ne correspondent pas"}), 400
        
    success, error = auth_service.reset_password(email, code, new_password)
    if not success:
        return jsonify({"message": error}), 400
    return jsonify({"message": "Mot de passe mis à jour avec succès"}), 200
