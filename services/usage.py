# services/usage.py
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

class UsageTracker:
    def __init__(self, daily_limit: int, data_dir: Path = None):
        self.daily_limit = daily_limit
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(exist_ok=True)
        self.usage_file = self.data_dir / "usage.json"
        self.usage = self._load()
    
    def _load(self) -> dict:
        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save(self):
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
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
    
    def check_limit(self, user_id: int) -> bool:
        used = self.get_count(user_id)
        return used < self.daily_limit
    
    def increment(self, user_id: int) -> bool:
        if not self.check_limit(user_id):
            return False
        uid = str(user_id)
        today = self._today()
        if uid not in self.usage or self.usage[uid].get('date') != today:
            self.usage[uid] = {'date': today, 'count': 1}
        else:
            self.usage[uid]['count'] = self.usage[uid].get('count', 0) + 1
        self._save()
        return True
    
    def get_stats_text(self, user_id: int) -> str:
        used = self.get_count(user_id)
        remaining = self.daily_limit - used
        today = self._today()
        percent = (used / self.daily_limit) * 100 if self.daily_limit > 0 else 0
        bar = "█" * int(20 * percent / 100) + "░" * (20 - int(20 * percent / 100))
        return (
            f"📊 **Статистика**\n"
            f"📅 `{today}`\n"
            f"📈 [{bar}] {percent:.0f}%\n"
            f"✅ `{used}` / ❌ `{remaining}` из `{self.daily_limit}`"
        )
    
    # Алиасы для совместимости
    def can_generate(self, user_id: int) -> bool:
        return self.check_limit(user_id)
    
    def get_usage(self, user_id: int) -> int:
        return self.get_count(user_id)
    
    def record_generation(self, user_id: int) -> bool:
        return self.increment(user_id)
