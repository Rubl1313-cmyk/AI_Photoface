# services/usage.py
from datetime import datetime, timedelta
from collections import defaultdict

class UsageTracker:
    def __init__(self, daily_limit: int):
        self.daily_limit = daily_limit
        self.usage = defaultdict(list)
    
    def _get_today(self) -> str:
        return datetime.now().date().isoformat()
    
    def check_limit(self, user_id: int) -> bool:
        today = self._get_today()
        self.usage[user_id] = [d for d in self.usage[user_id] if d == today]
        return len(self.usage[user_id]) < self.daily_limit
    
    def increment(self, user_id: int) -> bool:
        if not self.check_limit(user_id):
            return False
        self.usage[user_id].append(self._get_today())
        return True
