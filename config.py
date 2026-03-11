# config.py
import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения
load_dotenv()

# 🔑 TELEGRAM
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# 🔑 WEBHOOK (HF Spaces)
SPACE_ID = os.getenv("SPACE_ID", "")  # ваш-username/ai-photostudio
WEBHOOK_PATH = "/webhook"
if SPACE_ID:
    WEBHOOK_URL = f"https://{SPACE_ID}.hf.space{WEBHOOK_PATH}"
else:
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

# 🔑 LIMITS
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "50"))

# 🔑 EXTERNAL APIS
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "https://Dmitry1313-facefusion-api.hf.space").strip()

# 🔑 BOT INFO
BOT_NAME = "🎨 AI PhotoStudio"

# 🔑 DATA DIRECTORY (HF Spaces)
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(exist_ok=True)
