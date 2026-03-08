import os, sys
from dotenv import load_dotenv
from pymongo import MongoClient

# Add current directory to path
sys.path.append(os.getcwd())

load_dotenv()

def check_db():
    uri = os.getenv('MONGODB_URI')
    client = MongoClient(uri)
    db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
    db = client[db_name]
    
    colls = db.list_collection_names()
    if 'users' in colls:
        users = list(db.users.find())
        print(f"Total Users in DB: {len(users)}")
        if len(users) > 0:
            for i, u in enumerate(users[:3]):
                u_clean = {k:v for k,v in u.items() if k != 'password'}
                print(f"User {i} keys: {list(u_clean.keys())}")
                print(f"User {i} data: {u_clean}")
    else:
        print("CRITICAL: 'users' collection NOT FOUND")

if __name__ == "__main__":
    check_db()

if __name__ == "__main__":
    check_db()
