# config.py
import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения
load_dotenv()

# 🔑 TELEGRAM (поддержка старых и новых названий)
BOT_TOKEN = os.getenv("BOT_TOKEN", os.getenv("TG_BOT_TOKEN", "")).strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# 🔑 WEBHOOK
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

# 🔑 LIMITS
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "50"))

# 🔑 EXTERNAL APIS
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

# 🔑 BOT INFO
BOT_NAME = os.getenv("BOT_NAME", "🎨 AI PhotoStudio")

# 🔑 DATA DIRECTORY
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(exist_ok=True)
