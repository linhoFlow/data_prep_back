import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
db = client[db_name]

users = list(db.users.find())
print(f"Total users: {len(users)}")

clients = [u for u in users if u.get('role') not in ['admin', 'manager']]
print(f"Clients (not admin/manager): {len(clients)}")

for u in users:
    print(f"- ID: {u['_id']} | Role: '{u.get('role')}' | Name: {u.get('name')}")

print("\nChecking specifically for 'user' role:")
user_role_count = db.users.count_documents({"role": "user"})
print(f"Count of users with 'role' == 'user': {user_role_count}")

print("\nChecking for missing/null role:")
null_count = db.users.count_documents({"role": None})
missing_count = db.users.count_documents({"role": {"$exists": False}})
print(f"Null: {null_count}, Missing: {missing_count}")
