from app.repositories.base_repository import BaseRepository

class SessionRepository(BaseRepository):
    def __init__(self):
        super().__init__('preprocessing_sessions')

    def find_by_user(self, user_id):
        return list(self.collection.find({"user_id": user_id}).sort("updated_at", -1))

    def update_session(self, session_id, user_id, data):
        # Ensure user owns the session
        from bson import ObjectId
        self.collection.update_one(
            {"_id": ObjectId(session_id), "user_id": user_id},
            {"$set": data}
        )
