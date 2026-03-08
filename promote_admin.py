import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def promote_to_admin(email):
    uri = os.getenv('MONGODB_URI')
    client = MongoClient(uri)
    db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
    db = client[db_name]
    
    result = db.users.update_one(
        {"email": email},
        {"$set": {"role": "admin", "tier": "enterprise"}}
    )
    
    if result.matched_count > 0:
        print(f"SUCCÈS : L'utilisateur {email} est maintenant ADMINISTRATEUR.")
    else:
        print(f"ERREUR : Utilisateur avec l'email {email} non trouvé.")

if __name__ == "__main__":
    email = input("Entrez l'email de l'utilisateur à promouvoir en Admin : ")
    promote_to_admin(email)
