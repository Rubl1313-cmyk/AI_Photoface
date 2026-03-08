#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — FastAPI App for Hugging Face Spaces
Webhook handler for Telegram Bot
"""
import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from aiogram import Bot, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

# Импорт роутеров из main.py
from main import dp, process_update_safe, bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI PhotoStudio Bot",
    description="Telegram Bot with AI Photo Generation",
    version="2.0.0"
)

# =============================================================================
# 🔧 HEALTH & PING (чтобы Space не засыпал)
# =============================================================================
@app.get("/")
async def root():
    """Главная страница"""
    return HTMLResponse("""
    <html>
        <head><title>🎨 AI PhotoStudio Bot</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>🚀 AI PhotoStudio Bot is Running!</h1>
            <p>✅ Webhook active</p>
            <p>📊 Version: 2.0.0</p>
            <p>⏰ Time: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        </body>
    </html>
    """)

@app.get("/health")
async def health():
    """Эндпоинт для пинга (чтобы Space не засыпал)"""
    return JSONResponse({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime": "running"
    })

@app.get("/ping")
async def ping():
    """Альтернативный пинг"""
    return JSONResponse({"ok": True, "message": "pong"})

# =============================================================================
# 📡 TELEGRAM WEBHOOK
# =============================================================================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Получает обновления от Telegram"""
    try:
        body = await request.body()
        update = types.Update.model_load_json(body.decode())
        
        # Feed update в dispatcher
        await dp.feed_update(bot, update)
        
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse({"ok": False, "error": str(e)})

# =============================================================================
# 📊 STATS & DEBUG
# =============================================================================
@app.get("/stats")
async def get_stats():
    """Статистика бота"""
    return JSONResponse({
        "bot_username": (await bot.get_me()).username,
        "timestamp": datetime.now().isoformat(),
        "status": "running"
    })

@app.get("/set-webhook")
async def set_webhook():
    """Установить вебхук (вызвать один раз после деплоя)"""
    try:
        hf_space = os.getenv("SPACE_ID", "your-username/ai-photostudio")
        webhook_url = f"https://{hf_space}.hf.space/webhook"
        
        result = await bot.set_webhook(
            webhook_url,
            allowed_updates=["message", "callback_query", "chat_member"]
        )
        
        return JSONResponse({
            "ok": result,
            "webhook_url": webhook_url
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# =============================================================================
# 🚀 STARTUP
# =============================================================================
@app.on_event("startup")
async def startup_event():
    """При старте приложения"""
    logger.info("🚀 AI PhotoStudio Bot starting...")
    
    # Автоматически устанавливаем вебхук
    try:
        hf_space = os.getenv("SPACE_ID", "")
        if hf_space:
            webhook_url = f"https://{hf_space}.hf.space/webhook"
            await bot.set_webhook(
                webhook_url,
                allowed_updates=["message", "callback_query", "chat_member"]
            )
            logger.info(f"✅ Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """При остановке приложения"""
    logger.info("🛑 Bot shutting down...")
    await bot.session.close()
