import os
from dotenv import load_dotenv

load_dotenv()

# 🔥 Обязательные переменные
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "").strip()
CF_API_KEY = os.getenv("CF_API_KEY", "").strip()

# 🔥 Опциональные переменные
BOT_NAME = os.getenv("BOT_NAME", "🎨 AI PhotoStudio")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "50"))
PORT = int(os.getenv("PORT", "8080"))  # Render: 8080 для веб-сервисов
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "http://localhost:8081")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

# 🔥 Для Render (опционально, если хочешь webhook)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

def check_config():
    """Проверка наличия обязательных переменных"""
    errors = []
    if not TG_BOT_TOKEN or len(TG_BOT_TOKEN) < 40:
        errors.append("❌ TG_BOT_TOKEN не установлен")
    if not CF_WORKER_URL:
        errors.append("❌ CF_WORKER_URL не установлен")
    if not CF_API_KEY:
        errors.append("❌ CF_API_KEY не установлен")
    
    if errors:
        for e in errors:
            print(e)
        return False
    print("✅ Конфигурация проверена")
    return True