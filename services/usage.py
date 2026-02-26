import json
import os
from datetime import datetime, timezone

USAGE_FILE = "/tmp/usage.json"  # Render имеет эфемерную файловую систему

class UsageTracker:
    def __init__(self, daily_limit: int = 50):
        self.daily_limit = daily_limit
        self.usage = self._load()

    def _load(self):
        if os.path.exists(USAGE_FILE):
            try:
                with open(USAGE_FILE, "r") as f:
                    data = json.load(f)
                # Проверяем дату, если не сегодня – сбрасываем
                if data.get("date") != self._today_str():
                    return {"date": self._today_str(), "users": {}}
                return data
            except:
                pass
        return {"date": self._today_str(), "users": {}}

    def _save(self):
        with open(USAGE_FILE, "w") as f:
            json.dump(self.usage, f)

    def _today_str(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def check_limit(self, user_id: int) -> bool:
        return self.get_usage(user_id) < self.daily_limit

    def get_usage(self, user_id: int) -> int:
        return self.usage["users"].get(str(user_id), 0)

    def increment(self, user_id: int) -> bool:
        current = self.get_usage(user_id)
        if current >= self.daily_limit:
            return False
        self.usage["users"][str(user_id)] = current + 1
        self._save()
        return True
