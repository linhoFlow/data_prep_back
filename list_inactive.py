import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
db = client[db_name]

print(f"--- INACTIVE USERS ---")
inactive = list(db.users.find({"is_active": False}))
for u in inactive:
    print(f"- {u.get('name')} | {u.get('email')} | Role: {u.get('role')} | Tier: {u.get('tier')}")

if len(inactive) == 0:
    print("No inactive users found.")
