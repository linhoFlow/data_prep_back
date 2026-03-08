import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
db = client[db_name]

print(f"Repairing users in DB: {db_name}")

# 1. Update users with missing role
res_role = db.users.update_many(
    {"role": {"$exists": False}},
    {"$set": {"role": "user"}}
)
print(f"Users with missing role updated: {res_role.modified_count}")

res_role_null = db.users.update_many(
    {"role": None},
    {"$set": {"role": "user"}}
)
print(f"Users with null role updated: {res_role_null.modified_count}")

# 2. Update users with missing created_at
# We'll set them to a date a few days ago so they appear in 'this month' but maybe not 'this week'
some_date = (datetime.utcnow() - timedelta(days=5)).isoformat()
res_date = db.users.update_many(
    {"created_at": {"$exists": False}},
    {"$set": {"created_at": some_date}}
)
print(f"Users with missing created_at updated: {res_date.modified_count}")

print("Repair complete!")
