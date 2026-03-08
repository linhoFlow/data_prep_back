import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
db = client[db_name]

print(f"--- STAFF ACCOUNTS ---")
staff = list(db.users.find({"role": {"$in": ["admin", "manager"]}}))
for u in staff:
    print(f"- {u.get('name')} | {u.get('email')} | Role: {u.get('role')} | Tier: {u.get('tier')}")

print(f"\n--- ALL ROLES ---")
print(db.users.distinct("role"))

print(f"\n--- SAMPLE CLIENTS ---")
clients = list(db.users.find({"role": "user"}).limit(5))
for c in clients:
    print(f"- {c.get('name')} | {c.get('email')}")
