import bcrypt
import os
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from flask_jwt_extended import create_access_token
from datetime import timedelta

class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.email_service = EmailService()

    def register_user(self, name, email, password, role="user"):
        if self.user_repo.find_by_email(email):
            return None, "L'utilisateur existe déjà"
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Par défaut, les gestionnaires sont inactifs
        is_active = True if role != "manager" else False
        
        from datetime import datetime
        user_id = self.user_repo.create({
            "name": name,
            "email": email,
            "password": hashed_password.decode('utf-8'),
            "tier": "starter",
            "role": role,
            "is_active": is_active,
            "created_at": datetime.utcnow().isoformat()
        })

        # Notifier l'admin si c'est un gestionnaire
        if role == "manager":
            # On cherche l'admin principal pour le notifier (premier admin trouvé)
            users = self.user_repo.find_all()
            admin = next((u for u in users if u.get('role') == 'admin'), None)
            if admin:
                self.email_service.send_admin_new_manager_notification(
                    admin['email'], name, email
                )
                
        return user_id, None

    def login_user(self, email, password):
        user = self.user_repo.find_by_email(email)
        if not user:
            return None, "Identifiants incorrects"
        
        # Vérifier si le compte est actif
        if not user.get('is_active', True):
            return None, "Votre compte n'est pas encore activé. Veuillez contacter l'administrateur."
            
        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # Lire le tier et le rôle depuis MongoDB
            tier = user.get('tier', 'starter')
            role = user.get('role', 'user')
            token = create_access_token(
                identity=str(user['_id']),
                additional_claims={"tier": tier, "role": role}
            )
            return {
                "id": str(user['_id']),
                "name": user['name'],
                "email": user['email'],
                "token": token,
                "tier": tier,
                "role": role  # Envoyé au frontend
            }, None
        
        return None, "Identifiants incorrects"

    def guest_login(self):
        # Token invité sans expiration stricte (ou très longue)
        token = create_access_token(
            identity="guest_user",
            additional_claims={"tier": "guest", "role": "guest"},
            expires_delta=False # Désactiver l'expiration pour le mode invité
        )
        return {
            "id": "guest",
            "name": "Invité",
            "email": "guest@dataprep.pro",
            "token": token,
            "tier": "guest",
            "session_timeout_minutes": None # Plus de limite
        }, None

    def forgot_password(self, email):
        user = self.user_repo.find_by_email(email)
        if not user:
            return False, "Utilisateur non trouvé"
        
        code = self.email_service.generate_code()
        print(f"DEBUG: Generating code {code} for {email}")
        # Stockage temporaire du code dans le document user
        self.user_repo.update(str(user['_id']), {"reset_code": code})
        
        success, error = self.email_service.send_reset_code(email, code)
        if not success:
            return False, f"Erreur d'envoi d'email : {error}"
            
        return True, None

    def verify_reset_code(self, email, code):
        user = self.user_repo.find_by_email(email)
        if not user:
            print(f">>> [AUTH DEBUG] Verify Code: User {email} NOT FOUND")
            return False, "Utilisateur non trouvé"
            
        stored_code = user.get('reset_code')
        print(f">>> [AUTH DEBUG] Verify Code: Email={email}, Provided={code}, Stored={stored_code}")
        
        if stored_code != code:
            return False, "Code invalide ou expiré"
        return True, None

    def reset_password(self, email, code, new_password):
        user = self.user_repo.find_by_email(email)
        if not user or user.get('reset_code') != code:
            return False, "Session de réinitialisation invalide"
            
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        self.user_repo.update(str(user['_id']), {
            "password": hashed_password.decode('utf-8'),
            "reset_code": None # Invalider le code après usage
        })
        return True, None
