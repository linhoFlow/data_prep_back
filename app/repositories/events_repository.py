from app.repositories.base_repository import BaseRepository

class EventsRepository(BaseRepository):
    def __init__(self):
        super().__init__('admin_events')

    def find_upcoming(self, limit=5):
        from datetime import datetime
        return list(self.collection.find({
            "event_date": {"$gte": datetime.utcnow().isoformat()}
        }).sort("event_date", 1).limit(limit))
