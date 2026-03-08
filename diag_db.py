import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
db = client[db_name]

print(f"Connected to DB: {db_name}")
users_count = db.users.count_documents({})
print(f"Total users in DB: {users_count}")

distinct_roles = db.users.distinct("role")
print(f"Distinct roles: {distinct_roles}")

for role in distinct_roles:
    count = db.users.count_documents({"role": role})
    print(f"Role '{role}': {count}")

# Samples
print("\nSample Users:")
for u in db.users.find().limit(5):
    print(f"- {u.get('name')} | Role: {u.get('role')} | Tier: {u.get('tier')} | CreatedAt: {u.get('created_at')}")

datasets_count = db.datasets.count_documents({})
print(f"\nTotal datasets in DB: {datasets_count}")

sessions_count = db.preprocessing_sessions.count_documents({})
print(f"Total sessions in DB: {sessions_count}")
