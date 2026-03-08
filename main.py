#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot Logic (HF Spaces Edition)
- Обновлённые пути для хранения данных
- Интеграция с FastAPI через app.py
"""
import asyncio
import logging
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from aiogram import Bot, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, ReplyKeyboardRemove
from deep_translator import GoogleTranslator

import config
from states import UserStates
from keyboards import get_main_menu, get_gender_keyboard, get_style_keyboard, get_shot_type_keyboard, get_reply_keyboard
from services.cloudflare import (
    generate_with_cloudflare,
    generate_inpainting_photoshoot,
    truncate_caption
)
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# ------------------------------------------------------------
# Константы
# ------------------------------------------------------------
SWAP_OWN_BUTTON = "🖼️ Замена лица на своём изображении"
PHOTOSHOOT_BUTTON = "✨ ИИ фотосессия"
MAX_PROMPT_LENGTH = 1024
MAX_CAPTION_LENGTH = 1024

# 🔑 HF Spaces: используем относительный путь для данных
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_REALISTIC_PROMPT = (
    "looking into the camera, professional photography, photorealistic, sharp focus, 8k uhd, "
    "dslr, soft lighting, high quality, film grain, natural skin texture, "
    "realistic details, depth of field, bokeh, studio lighting"
)

STYLE_PROMPTS = {
    "style_photorealistic": "like a real photo, photorealistic, professional photography",
    "style_hyperrealistic": "like a real photo, hyperrealistic, ultra detailed, 8k resolution",
    "style_cinematic": "cinematic shot, movie still, dramatic lighting",
    "style_art": "artistic, creative interpretation",
    "style_oil_painting": "oil painting, classical art style",
    "style_watercolor": "watercolor painting, soft edges",
    "style_sketch": "pencil sketch, black and white drawing",
    "style_cyberpunk": "cyberpunk, neon lights, futuristic city",
    "style_fantasy": "fantasy art, magical, epic atmosphere",
    "style_scifi": "science fiction, futuristic technology",
    "style_space": "space, cosmic, stellar background",
    "style_vintage": "vintage, retro, old photo style",
    "style_noir": "film noir, black and white, dramatic shadows",
    "style_popart": "pop art, vibrant colors, warhol style",
    "style_comic": "comic book style, graphic novel",
    "style_anime": "anime style, manga, japanese animation",
    "style_3d_render": "3D render, CGI, digital art",
    "style_pixel_art": "pixel art, 8-bit, retro game style",
    "style_impressionism": "impressionist painting, monet style",
    "style_classical": "classical art, renaissance style",
    "style_surrealism": "surrealism, dali style, dreamlike",
}

# ------------------------------------------------------------
# Логирование
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Инициализация
# ------------------------------------------------------------
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
facefusion_client = FaceFusionClient(api_url=config.FACEFUSION_URL)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT, data_dir=DATA_DIR)

# ------------------------------------------------------------
# УНИВЕРСАЛЬНЫЕ ФУНКЦИИ
# ------------------------------------------------------------
async def send_message(event, text: str, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        return await event.message.answer(text, reply_markup=reply_markup)
    else:
        return await event.reply(text, reply_markup=reply_markup)

async def send_photo(event, photo, caption: str = None, reply_markup=None):
    if caption:
        caption = truncate_caption(caption, max_length=MAX_CAPTION_LENGTH)
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        return await event.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    else:
        return await event.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup)

async def edit_message(event: types.CallbackQuery, text: str, reply_markup=None):
    if reply_markup is not None:
        return await event.message.edit_text(text, reply_markup=reply_markup)
    else:
        return await event.message.edit_text(text)

def validate_prompt_length(prompt: str, max_length: int = MAX_PROMPT_LENGTH):
    if not prompt or len(prompt.strip()) == 0:
        return False, "❌ Промпт не может быть пустым."
    if len(prompt) > max_length:
        return False, f"❌ Промпт слишком длинный (максимум {max_length} символов)."
    return True, ""

# ------------------------------------------------------------
# Обработчики (сокращённая версия — полные из вашего main.py)
# ------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    await message.answer("🔄 Обновляю интерфейс...", reply_markup=ReplyKeyboardRemove())
    
    await message.answer(
        f"👋 Привет! Я {config.BOT_NAME}\n\n"
        "🔄 **С заменой лица**: фото → генерация → твоё лицо\n"
        "✨ **Просто генерация**: изображение по тексту\n"
        f"{SWAP_OWN_BUTTON}: меняю лицо на твоём фото\n"
        f"{PHOTOSHOOT_BUTTON}: фотосессия с твоим лицом\n\n"
        "📝 Промпт максимум 1024 символа.\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )
    
    await message.answer(
        "💡 Также можно использовать кнопки внизу 👇",
        reply_markup=get_reply_keyboard()
    )
    
    logger.info(f"🚀 /start by user {message.from_user.id}")

# ... ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ИЗ ВАШЕГО main.py БЕЗ ИЗМЕНЕНИЙ ...
# (receive_face_photo, process_gender, process_style, etc.)

# ------------------------------------------------------------
# Для импорта в app.py
# ------------------------------------------------------------
async def process_update_safe(update_data: dict):
    """Безопасная обработка обновления (для webhook)"""
    try:
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"❌ Process update error: {e}")

# Экспортируем dp для app.py
from aiogram import Dispatcher
dp = Dispatcher(storage=storage)
