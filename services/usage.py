import json
import os
from datetime import datetime, timezone

USAGE_FILE = "/data/usage.json"  # Render: используем /data для постоянных данных

class UsageTracker:
    def __init__(self, daily_limit: int = 50):
        self.daily_limit = daily_limit
        self.usage = self._load()
    
    def _load(self) -> dict:
        try:
            if os.path.exists(USAGE_FILE):
                with open(USAGE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save(self):
        try:
            os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
            with open(USAGE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.usage, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    def get_count(self, user_id: int) -> int:
        uid = str(user_id)
        today = self._today()
        if uid not in self.usage or self.usage[uid].get('date') != today:
            self.usage[uid] = {'date': today, 'count': 0}
            self._save()
            return 0
        return self.usage[uid].get('count', 0)
    
    def can_generate(self, user_id: int) -> tuple[bool, int]:
        used = self.get_count(user_id)
        remaining = self.daily_limit - used
        return remaining > 0, remaining
    
    def increment(self, user_id: int):
        uid = str(user_id)
        today = self._today()
        if uid not in self.usage or self.usage[uid].get('date') != today:
            self.usage[uid] = {'date': today, 'count': 1}
        else:
            self.usage[uid]['count'] = self.usage[uid].get('count', 0) + 1
        self._save()
    
    def get_stats_text(self, user_id: int) -> str:
        used = self.get_count(user_id)
        remaining = self.daily_limit - used
        today = self._today()
        percent = (used / self.daily_limit) * 100 if self.daily_limit > 0 else 0
        bar = "█" * int(20 * percent / 100) + "░" * (20 - int(20 * percent / 100))
        return (
            f"📊 **Статистика**\n\n"
            f"📅 `{today}`\n"
            f"📈 [{bar}] {percent:.0f}%\n"
            f"✅ `{used}` / ❌ `{remaining}` из `{self.daily_limit}`"
        )

tracker = UsageTracker(daily_limit=int(os.getenv("DAILY_LIMIT", "50")))