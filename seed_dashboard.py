import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('MONGODB_URI')
client = MongoClient(uri)
db_name = uri.split('/')[-1].split('?')[0] or 'data_prep_pro'
db = client[db_name]

# 1. Clear existing events to avoid duplicates
db.admin_events.delete_many({})

# 2. Add sample events
events = [
    {
        "title": "Mise à jour serveurs (02:00)",
        "event_date": (datetime.utcnow() + timedelta(days=9)).isoformat(),
        "type": "maintenance"
    },
    {
        "title": "Revue trimestrielle clients",
        "event_date": (datetime.utcnow() + timedelta(days=16)).isoformat(),
        "type": "event"
    }
]
db.admin_events.insert_many(events)

# 3. Add sample chat history if empty
if db.chat_history.count_documents({}) == 0:
    # Need a user ID to associate with
    user = db.users.find_one({"role": "user"})
    if user:
        db.chat_history.insert_one({
            "user_id": user['_id'],
            "conversation_id": "seed-conv-1",
            "title": "Problème d'exportation CSV",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "messages": [
                {"role": "user", "content": "Comment exporter en format Excel ?", "timestamp": datetime.utcnow().isoformat()},
                {"role": "bot", "content": "Vous pouvez cliquer sur le bouton 'Exporter' en haut à droite...", "timestamp": datetime.utcnow().isoformat()}
            ]
        })

print("Dashboard seeded successfully!")
proxy_stats = db.admin_events.count_documents({})
print(f"Total events in DB: {proxy_stats}")
