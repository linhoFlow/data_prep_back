from app.repositories.base_repository import BaseRepository

class DatasetRepository(BaseRepository):
    def __init__(self):
        super().__init__('datasets')

    def find_by_user(self, user_id):
        return list(self.collection.find({"user_id": user_id}))
