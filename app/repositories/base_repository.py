from flask import current_app
from bson import ObjectId

class BaseRepository:
    def __init__(self, collection_name):
        self.collection_name = collection_name

    @property
    def collection(self):
        # We use current_app.db which was attached in create_app
        if not hasattr(current_app, 'db') or current_app.db is None:
            raise RuntimeError("Database not initialized on current_app. Check app/__init__.py initialization.")
        return current_app.db[self.collection_name]

    def find_all(self):
        return list(self.collection.find())

    def find_by_id(self, item_id):
        return self.collection.find_one({"_id": ObjectId(item_id)})

    def find_one(self, query):
        return self.collection.find_one(query)

    def create(self, data):
        result = self.collection.insert_one(data)
        return str(result.inserted_id)

    def update(self, item_id, data):
        result = self.collection.update_one({"_id": ObjectId(item_id)}, {"$set": data})
        return result.modified_count > 0 or result.matched_count > 0

    def delete(self, item_id):
        result = self.collection.delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0
