import os
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongo_client = None
db = None

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret')
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB Limit
    app.config['SWAGGER'] = {
        'title': 'DataPrep Pro API',
        'uiversion': 3
    }

    # Extensions
    CORS(app, expose_headers=['Content-Disposition', 'Content-Type', 'X-Suggested-Filename'])
    Swagger(app)
    JWTManager(app)

    # MongoDB Init
    global mongo_client, db
    uri = os.getenv('MONGODB_URI')
    print(f"[INIT] Connecting to MongoDB...", flush=True)
    try:
        mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Extract DB name from URI or use default
        db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
        db = mongo_client[db_name]
        # Test connection
        mongo_client.admin.command('ping')
        print(f"[INIT] MongoDB connected to database: {db_name}", flush=True)
        app.db = db # Attach to app object for cross-module access
    except Exception as e:
        print(f"[ERROR] MongoDB connection failed: {str(e)}", flush=True)
        # We continue to let the app start, but DB dependent routes will fail

    print("[INIT] Registering Blueprints...", flush=True)
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    print("[INIT] Auth blueprint registered.", flush=True)

    from app.routes.datasets import datasets_bp
    app.register_blueprint(datasets_bp, url_prefix='/api/datasets')
    print("[INIT] Datasets blueprint registered.", flush=True)

    from app.routes.sessions import sessions_bp
    app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
    print("[INIT] Sessions blueprint registered.", flush=True)

    from app.routes.chat import chat_bp
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    print("[INIT] Chat blueprint registered.", flush=True)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    print("[INIT] Admin blueprint registered.", flush=True)

    @app.route('/health')
    def health():
        return {'status': 'healthy', 'mongodb': 'connected' if mongo_client else 'disconnected', 'version': 'V3.2-RELIANT'}

    return app
