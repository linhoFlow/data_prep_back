import os
from flask import Flask
from flask_jwt_extended import create_access_token, JWTManager
from pymongo import MongoClient
from dotenv import load_dotenv
import requests
import json

load_dotenv()

# We need a Flask app to create a token
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret')
jwt = JWTManager(app)

def get_admin_token():
    uri = os.getenv('MONGODB_URI')
    client = MongoClient(uri)
    db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
    db = client[db_name]
    
    admin = db.users.find_one({"role": "admin"})
    if not admin:
        print("No admin found in DB!")
        return None
    
    with app.app_context():
        # Mirroring AuthService.py logic
        token = create_access_token(
            identity=str(admin['_id']),
            additional_claims={"tier": admin.get('tier', 'enterprise'), "role": "admin"}
        )
        return token

def test_stats_api(token):
    print(f"Testing stats API with token: {token[:20]}...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get("http://localhost:5000/api/admin/stats", headers=headers)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Total Users: {data.get('total_users')}")
            print(f"Clients Count: {data.get('clients_count')}")
            print(f"User Trend: {data.get('user_trend')}")
            print(f"Client Trend: {data.get('client_trend')}")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    t = get_admin_token()
    if t:
        test_stats_api(t)
