# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# 🔑 TELEGRAM
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# 🔑 WEBHOOK
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"https://ai-photoface.onrender.com{WEBHOOK_PATH}").strip()

# 🔑 LIMITS
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 10))

# 🔑 EXTERNAL APIS
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "https://Dmitry1313-facefusion-api.hf.space").strip()

# 🔑 BOT INFO
BOT_NAME = "🎨 AI PhotoStudio"
