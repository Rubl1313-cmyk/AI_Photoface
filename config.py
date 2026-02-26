import os
from dotenv import load_dotenv
load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "").strip()
CF_API_KEY = os.getenv("CF_API_KEY", "").strip()
BOT_NAME = os.getenv("BOT_NAME", "🎨 AI PhotoStudio")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "50"))
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "http://localhost:8081")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")  # ✅ Добавь эту строку

def check_config():
    if not TG_BOT_TOKEN or len(TG_BOT_TOKEN) < 40: print("❌ TG_BOT_TOKEN"); return False
    if not CF_WORKER_URL: print("❌ CF_WORKER_URL"); return False
    if not CF_API_KEY: print("❌ CF_API_KEY"); return False
    print("✅ Конфигурация проверена"); return True
