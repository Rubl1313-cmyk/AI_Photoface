#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Telegram бот для Render.com
✅ Polling режим (работает на Render без проблем с DNS)
✅ Полный UI с кнопками, меню, стилями
✅ user_ dict = {} (ПРАВИЛЬНЫЙ СИНТАКСИС — проверено!)
✅ Отправляет full_prompt в Cloudflare (BASE + пользовательский + стиль)
✅ Обработка ошибок FaceFusion с понятными сообщениями
"""

import asyncio
import logging
import os
import signal
import sys
import time

from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, BotCommand, BotCommandScopeDefault,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

# 🔥 Загрузка переменных окружения
load_dotenv()

# 🔥 Импорт конфигурации
from config import (
    TG_BOT_TOKEN, CF_WORKER_URL, CF_API_KEY,
    BOT_NAME, DAILY_LIMIT, PORT, FACEFUSION_URL,
    check_config
)
from states import UserStates
from keyboards import get_main_menu, get_style_menu, get_result_keyboard
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import tracker

# 🔥 Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================================================
# ✅ ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ — ПРАВИЛЬНЫЙ СИНТАКСИС
# ============================================================================

bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher()
face_swapper = None
user_data: dict = {}  # ✅ ПРАВИЛЬНО: user_ dict = {} (underscore + colon + dict)

# ============================================================================
# 🔥 ПРОМПТЫ — УСИЛЕННЫЙ BASE_FACE_PROMPT
# ============================================================================

STYLE_PROMPTS = {
    "style_cinematic": "cinematic lighting, dramatic, film grain",
    "style_portrait": "professional portrait, studio lighting, soft shadows",
    "style_art": "digital art, illustration, vibrant colors",
    "style_realistic": "photorealistic, natural lighting, sharp focus",
    "style_cyberpunk": "neon lights, cyberpunk, futuristic",
    "style_fantasy": "fantasy art, magical, ethereal lighting",
}

# 🔥 УСИЛЕННЫЙ: без "looking at camera", с жёсткими ограничениями на лицо
BASE_FACE_PROMPT = (
    "portrait of a person, clear face, professional photo, "
    "sharp focus, face centered, high quality, detailed face, "
    "no hands in frame, no body parts visible, face only, "
    "headshot, upper body only, clean background, studio lighting"
)

# ============================================================================
# 🤖 ХЕНДЛЕРЫ БОТА
# ============================================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_data.pop(message.from_user.id, None)
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я — **{BOT_NAME}** 🎨\n"
        f"• Генерация фото по описанию\n"
        f"• Замена лица на сгенерированном\n"
        f"• {DAILY_LIMIT} генераций/день\n\n"
        f"🚀 Нажми «🎨 Создать фото»!",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    await message.answer(
        tracker.get_stats_text(message.from_user.id),
        parse_mode="Markdown"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        f"❓ **Помощь — {BOT_NAME}**\n\n"
        f"🎨 **Как создать фото:**\n"
        f"1. Нажми «🎨 Создать фото»\n"
        f"2. Отправь фото лица (анфас, хорошее освещение)\n"
        f"3. Напиши описание (например: `businessman in office`)\n"
        f"4. Выбери стиль или пропусти\n"
        f"5. Жди ~30-60 секунд — готово!\n\n"
        f"💡 **Советы:**\n"
        f"• Фото лица: крупный план, анфас, без фильтров\n"
        f"• Промпт: пиши на любом языке — я переведу\n\n"
        f"📊 **Лимиты:**\n"
        f"• {DAILY_LIMIT} генераций в день\n"
        f"• Сброс в 00:00 UTC"
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(F.text == "🎨 Создать фото")
async def start_creation(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    allowed, remaining = tracker.can_generate(user_id)
    
    if not allowed:
        await message.answer(
            f"❌ **Лимит исчерпан!**\n\n"
            f"Попробуй завтра после 00:00 UTC 🕐",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
        return
    
    await state.set_state(UserStates.waiting_for_face)
    user_data[user_id] = {'face': None}
    
    await message.answer(
        "📸 **Отправь фото лица**\n\n"
        "💡 Крупный план, анфас, хорошее освещение, без фильтров",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


@dp.message(UserStates.waiting_for_face, F.photo)
@dp.message(UserStates.waiting_for_face, F.document)
async def handle_face_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        file = message.photo[-1] if message.photo else message.document
        
        if message.document and not message.document.mime_type.startswith('image/'):
            await message.answer("❌ Это не изображение", parse_mode="Markdown")
            return
        
        downloaded = await bot.download(file)
        photo_bytes = downloaded.read()
        
        if len(photo_bytes) > 10_000_000:
            await message.answer("❌ Фото слишком большое (>10MB)", parse_mode="Markdown")
            return
        
        user_data[user_id]['face'] = photo_bytes
        
        await state.set_state(UserStates.waiting_for_prompt)
        await message.answer(
            "📝 **Напиши описание**\n💡 Пример: `businessman in office`",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"💥 Ошибка обработки фото: {e}")
        await message.answer("❌ Ошибка. Попробуй ещё раз", parse_mode="Markdown")


@dp.message(UserStates.waiting_for_prompt, F.text)
async def handle_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    if len(prompt) < 3 or len(prompt) > 200:
        await message.answer("❌ 3-200 символов", parse_mode="Markdown")
        return
    
    await state.update_data(prompt=prompt)
    await state.set_state(UserStates.choosing_style)
    await message.answer("🎨 **Выбери стиль:**", reply_markup=get_style_menu(), parse_mode="Markdown")


@dp.callback_query(UserStates.choosing_style, F.data.startswith("style_"))
async def style_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    user_id = callback.from_user.id
    style = callback.data
    style_name = style.replace("style_", "")
    
    await callback.message.edit_text(
        f"⏳ **Генерация...**\n\n"
        f"📝 `{data['prompt']}`\n"
        f"🎨 Стиль: `{style_name}`\n\n"
        f"⏱️ ~30-60 секунд",
        parse_mode="Markdown"
    )
    
    await state.set_state(UserStates.generating)
    await state.update_data(style=style)
    
    asyncio.create_task(generate_and_send(callback.message, user_id, data['prompt'], style))


@dp.callback_query(UserStates.choosing_style, F.data == "style_skip")
async def style_skip(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await style_selected(callback, state)


@dp.callback_query(F.data.startswith("back_to_main"))
async def go_home(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(UserStates.idle)
    
    try:
        await callback.message.edit_text(
            "🏠 **Главное меню**",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
    except:
        await callback.message.answer(
            "🏠 **Главное меню**",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )


@dp.callback_query(F.data.startswith("retry_"))
async def retry_generation(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    user_id = callback.from_user.id
    data = await state.get_data()
    
    if not data.get('prompt') or user_id not in user_data or not user_data[user_id].get('face'):
        await callback.message.answer("❌ Начни сначала", parse_mode="Markdown")
        await go_home(callback, state)
        return
    
    await callback.message.edit_text("🔄 **Повторная генерация...**", parse_mode="Markdown")
    
    asyncio.create_task(
        generate_and_send(callback.message, user_id, data['prompt'], data.get('style', 'style_realistic'))
    )


# ============================================================================
# 🎨 ОСНОВНАЯ ЛОГИКА ГЕНЕРАЦИИ — ИСПРАВЛЕНО: full_prompt в Cloudflare
# ============================================================================

async def generate_and_send(message: types.Message, user_id: int, prompt: str, style: str):
    try:
        allowed, _ = tracker.can_generate(user_id)
        if not allowed:
            await message.edit_text("❌ **Лимит исчерпан!**", parse_mode="Markdown")
            return
        
        user_face = user_data[user_id]['face']
        
        # 🔤 Перевод промпта на английский
        translator = GoogleTranslator(source='auto', target='en')
        translated = await asyncio.get_event_loop().run_in_executor(
            None, translator.translate, prompt
        )
        
        # 🔥 ФОРМИРУЕМ ПОЛНЫЙ ПРОМПТ: BASE + пользовательский + стиль
        style_text = STYLE_PROMPTS.get(style, "")
        full_prompt = f"{BASE_FACE_PROMPT}, {translated}, {style_text}".strip()
        logger.info(f"🎨 Промпт: {full_prompt[:150]}...")
        
        # 🎨 Шаг 1: Генерация — ✅ ОТПРАВЛЯЕМ full_prompt (НЕ только translated!)
        await message.edit_text("🎨 Шаг 1/3: Генерация...", parse_mode="Markdown")
        generated = await generate_with_cloudflare(
            prompt=full_prompt,  # ✅ ИСПРАВЛЕНО: было prompt=translated
            width=1024,
            height=1024,
            steps=4
        )
        
        if len(generated) < 1000:
            raise RuntimeError("Пустой ответ от генератора")
        
        # 👤 Шаг 2: Замена лица
        await message.edit_text("👤 Шаг 2/3: Замена лица...", parse_mode="Markdown")
        result, error = face_swapper.swap(user_face, generated)
        
        if error:
            logger.warning(f"⚠️ {error}")
            # Отправляем оригинальное сгенерированное изображение с предупреждением
            await message.answer(
                f"⚠️ **Замена лица не удалась**\n\n"
                f"📝 `{prompt}`\n"
                f"🎨 `{style.replace('style_', '') if style else 'без стиля'}`\n\n"
                f"🔄 Попробуй ещё раз или отправь другое фото лица",
                parse_mode="Markdown"
            )
            result = generated
        
        # ✅ Шаг 3: Отправка результата
        await message.edit_text("✅ Шаг 3/3: Готово!", parse_mode="Markdown")
        
        style_name = style.replace("style_", "") if style else "без стиля"
        
        await message.answer_photo(
            photo=BufferedInputFile(result, "result.png"),
            caption=f"📸 **Готово!**\n📝 `{prompt}`\n🎨 `{style_name}`",
            reply_markup=get_result_keyboard(f"gen_{user_id}_{int(time.time())}"),
            parse_mode="Markdown"
        )
        
        tracker.increment(user_id)
        user_data.pop(user_id, None)
        
        try:
            await message.delete()
        except:
            pass
        
        logger.info(f"✅ Генерация завершена для user_{user_id}")
        
    except TelegramAPIError as e:
        logger.error(f"💥 Telegram API ошибка: {e}")
        try:
            await message.edit_text(f"❌ Ошибка: {str(e)[:100]}", parse_mode="Markdown")
        except:
            await message.answer(f"❌ Ошибка: {str(e)[:100]}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"💥 Ошибка генерации: {e}", exc_info=True)
        try:
            await message.edit_text(f"❌ Ошибка: {str(e)[:150]}", parse_mode="Markdown")
        except:
            await message.answer(f"❌ Ошибка: {str(e)[:150]}", parse_mode="Markdown")
        user_data.pop(user_id, None)


# ============================================================================
# 🚀 POLLING РЕЖИМ — РАБОТАЕТ НА RENDER.COM
# ============================================================================

async def run_polling():
    """Polling режим с обработкой сетевых ошибок"""
    logger.info("🚀 Polling режим...")
    
    while True:
        try:
            logger.info("🔄 Start polling...")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except (TelegramNetworkError, TelegramAPIError) as e:
            logger.warning(f"⚠️ Telegram ошибка: {e}")
            logger.info("🔄 Повтор через 30 секунд...")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"💥 Polling crash: {e}", exc_info=True)
            logger.info("🔄 Повтор через 30 секунд...")
            await asyncio.sleep(30)


# ============================================================================
# 🎯 ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

async def main():
    """Главная функция запуска"""
    global face_swapper
    
    # 🔥 1. Проверка конфигурации
    if not check_config():
        logger.error("💥 Ошибка конфигурации")
        sys.exit(1)
    
    # 🔥 2. Инициализация сервисов
    face_swapper = FaceFusionClient(api_url=FACEFUSION_URL)
    
    # 🔥 3. Настройка команд бота (на Render работает!)
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀 Начать"),
            BotCommand(command="stats", description="📊 Статистика"),
            BotCommand(command="help", description="❓ Помощь"),
        ], scope=BotCommandScopeDefault())
        logger.info("✅ Команды настроены")
    except Exception as e:
        logger.warning(f"⚠️ Commands: {e}")
    
    # 🔥 4. Запуск polling
    logger.info(f"🚀 {BOT_NAME} | Polling режим (Render.com)")
    await run_polling()


# ============================================================================
# 🔥 ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Обработчики сигналов для graceful shutdown
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Прервано пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
