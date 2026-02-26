import os
from dotenv import load_dotenv

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "").strip()
CF_API_KEY = os.getenv("CF_API_KEY", "").strip()
BOT_NAME = os.getenv("BOT_NAME", "🎨 AI PhotoStudio")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "50"))
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # например https://ai-photoface.onrender.com
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PORT = int(os.getenv("PORT", "8080"))
