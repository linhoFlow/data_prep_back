import os
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def create_admin_account(email, password, name="Admin"):
    uri = os.getenv('MONGODB_URI')
    client = MongoClient(uri)
    db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
    db = client[db_name]
    
    # Vérifier si l'utilisateur existe déjà
    if db.users.find_one({"email": email}):
        print(f"L'utilisateur {email} existe déjà. Promotion en cours...")
        db.users.update_one(
            {"email": email},
            {"$set": {"role": "admin", "tier": "starter"}}
        )
        print("Promotion terminée.")
        return

    # Hacher le mot de passe
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    user_data = {
        "name": name,
        "email": email,
        "password": hashed_password.decode('utf-8'),
        "tier": "starter",
        "role": "admin"
    }
    
    db.users.insert_one(user_data)
    print(f"COMPTE ADMIN CRÉÉ AVEC SUCCÈS !")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print(f"Role: admin")
    print(f"Tier: starter")

if __name__ == "__main__":
    create_admin_account("admin@dataprep.pro", "AdminPass2026!")
