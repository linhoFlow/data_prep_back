import requests
import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:5000/api"

def get_admin_email():
    uri = os.getenv('MONGODB_URI')
    client = MongoClient(uri)
    db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
    db = client[db_name]
    admin = db.users.find_one({"role": "admin"})
    if admin:
        return admin['email']
    # If no admin, find any user and we'll trust the logic works for and role
    any_user = db.users.find_one()
    if any_user:
        return any_user['email']
    return None

def test_admin_access():
    email = get_admin_email()
    if not email:
        print("No users found in DB to test with.")
        return
        
    print(f"Testing with user: {email}")
    # Login
    login_data = {
        "email": email,
        "password": "AdminPass2026!" # This is what create_admin.py uses
    }
    r = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"Login Response ({r.status_code}): {r.text}")
    
    if r.status_code != 200:
        return
    
    token = r.json().get('token') # Fixed key
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test Users
    r = requests.get(f"{BASE_URL}/admin/users", headers=headers)
    print(f"Users Output ({r.status_code}): {r.text[:500]}...")
    if r.status_code == 200:
        users = r.json()
        print(f"SUCCESS: Found {len(users)} users")
        for u in users:
            print(f" - {u['email']} (role: {u.get('role', 'user')})")

if __name__ == "__main__":
    test_admin_access()
