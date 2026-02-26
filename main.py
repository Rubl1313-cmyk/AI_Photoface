#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot File
Supports:
- Face swapping with gender selection
- Simple image generation
- Document image uploads
- Colored inline buttons (Telegram API 9.4+)
- Admin startup notification
"""

import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config
from states import UserStates
from keyboards import (
    get_main_menu,
    get_gender_keyboard,
    get_style_keyboard,
)
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Clients
facefusion_client = FaceFusionClient(api_url=config.FACEFUSION_URL)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# ------------------------------------------------------------
# Startup notification to admin(s)
# ------------------------------------------------------------
async def send_startup_notification():
    """Send a message to admin(s) when the bot starts."""
    if not config.ADMIN_IDS:
        logger.info("No ADMIN_IDS configured, skipping startup notification")
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    render_url = config.WEBHOOK_URL or "not set"
    hf_url = config.FACEFUSION_URL or "not set"

    text = (
        f"🚀 *Bot {config.BOT_NAME} started\\!*\n\n"
        f"📅 *Time:* `{current_time}` UTC\n"
        f"🖥 *Render:* `{render_url}`\n"
        f"🎭 *FaceFusion:* `{hf_url}`\n"
        f"📊 *Daily limit:* `{config.DAILY_LIMIT}`\n\n"
        f"✅ Bot is ready\\!"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="MarkdownV2"
            )
            logger.info(f"Startup notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# ------------------------------------------------------------
# Command /start
# ------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    await message.answer(
        f"👋 Привет! Я {config.BOT_NAME}\n\n"
        "Я могу:\n"
        "🔄 **С заменой лица**: ты загружаешь фото лица, а я генерирую изображение по твоему описанию и вставляю это лицо.\n"
        "✨ **Просто генерация**: я создаю изображение только по текстовому описанию.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# ------------------------------------------------------------
# Main menu handlers
# ------------------------------------------------------------
@dp.message(lambda msg: msg.text == "🔄 С заменой лица")
async def create_photo_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Ты исчерпал дневной лимит. Завтра лимит обновится.")
        return

    await state.set_state(UserStates.waiting_for_face)
    await message.answer(
        "Отправь мне фото с лицом человека (можно как фото, так и файл-изображение).\n"
        "Лицо должно быть чётко видно."
    )

@dp.message(lambda msg: msg.text == "✨ Просто генерация")
async def simple_generation_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Ты исчерпал дневной лимит. Завтра лимит обновится.")
        return

    await state.set_state(UserStates.waiting_for_prompt_simple)
    await message.answer(
        "Напиши текстовое описание того, что нужно сгенерировать.\n"
        "Например: *красивый закат над горами, цифровое искусство*"
    )

@dp.message(lambda msg: msg.text == "📊 Моя статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    used = usage.get_usage(user_id)
    left = max(0, config.DAILY_LIMIT - used)
    await message.answer(
        f"📊 *Статистика:*\n"
        f"Использовано сегодня: `{used}` из `{config.DAILY_LIMIT}`\n"
        f"Осталось: `{left}`",
        parse_mode="MarkdownV2"
    )

@dp.message(lambda msg: msg.text == "❓ Помощь")
async def help_cmd(message: types.Message):
    await message.answer(
        "📖 *Помощь*\n\n"
        "**🔄 С заменой лица:**\n"
        "1\\. Нажми кнопку «🔄 С заменой лица»\n"
        "2\\. Отправь фото с лицом \\(или файл\\-изображение\\)\n"
        "3\\. Выбери пол человека\n"
        "4\\. Напиши промпт \\(описание сцены\\)\n"
        "5\\. Выбери стиль\n\n"
        "**✨ Просто генерация:**\n"
        "1\\. Нажми «✨ Просто генерация»\n"
        "2\\. Напиши промпт\n"
        "3\\. Выбери стиль\n\n"
        f"Дневной лимит: {config.DAILY_LIMIT} генераций",
        parse_mode="MarkdownV2"
    )

@dp.message(lambda msg: msg.text == "ℹ️ О боте")
async def about_cmd(message: types.Message):
    await message.answer(
        f"ℹ️ *О боте {config.BOT_NAME}*\n\n"
        "Этот бот создан для генерации изображений по тексту с возможностью замены лица на фотографии\\.\n\n"
        "🔹 *Технологии:*\n"
        "   • Генерация: Cloudflare Workers AI\n"
        "   • Замена лица: FaceFusion \\(Hugging Face\\)\n\n"
        f"🔹 *Лимиты:*\n"
        f"   • {config.DAILY_LIMIT} генераций в день на пользователя \\(сбрасывается в полночь по UTC\\)\n\n"
        "🔹 *Как использовать:*\n"
        "   Нажми «🔄 С заменой лица» или «✨ Просто генерация» и следуй инструкциям\\.\n\n"
        "По всем вопросам обращайтесь к администратору\\.",
        parse_mode="MarkdownV2"
    )

# ------------------------------------------------------------
# Face upload handlers (photo & document)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face, F.photo)
async def handle_face_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_bytes = await bot.download_file(file.file_path)
    await state.update_data(face_image=image_bytes.read())
    await state.set_state(UserStates.waiting_for_gender)
    await message.answer(
        "✅ Фото лица получено. Теперь укажи пол человека на фото:",
        reply_markup=get_gender_keyboard()
    )

@dp.message(UserStates.waiting_for_face, F.document)
async def handle_face_document(message: types.Message, state: FSMContext):
    if message.document.mime_type and message.document.mime_type.startswith('image/'):
        file = await bot.get_file(message.document.file_id)
        image_bytes = await bot.download_file(file.file_path)
        await state.update_data(face_image=image_bytes.read())
        await state.set_state(UserStates.waiting_for_gender)
        await message.answer(
            "✅ Изображение получено. Теперь укажи пол человека на фото:",
            reply_markup=get_gender_keyboard()
        )
    else:
        await message.answer("Пожалуйста, отправь изображение (фото или документ с картинкой).")

@dp.message(UserStates.waiting_for_face)
async def handle_face_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь фотографию или файл с изображением.")

# ------------------------------------------------------------
# Gender selection
# ------------------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await state.set_state(UserStates.waiting_for_prompt)
    await callback.message.edit_text(
        "✅ Пол учтён. Теперь напиши текстовое описание того, что должно быть на финальном изображении.\n"
        "Например: *в костюме на фоне космоса* (пол будет добавлен автоматически)"
    )

# ------------------------------------------------------------
# Prompt handling (with face)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt)
async def handle_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("Промпт не может быть пустым. Напиши описание.")
        return

    data = await state.get_data()
    gender = data.get("gender")
    gender_word = "мужчина" if gender == "male" else "женщина"
    # Prepend gender if not already present (simple check)
    if gender_word not in prompt.lower():
        prompt = f"{gender_word}, {prompt}"

    await state.update_data(prompt=prompt)
    await state.set_state(UserStates.choosing_style)
    await message.answer(
        "Выбери стиль для генерации:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Prompt handling (simple generation, no face)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_simple)
async def handle_simple_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("Промпт не может быть пустым. Напиши описание.")
        return
    await state.update_data(prompt=prompt)
    await state.set_state(UserStates.choosing_style)
    await message.answer(
        "Выбери стиль для генерации:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Style selection and final generation
# ------------------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("style_"))
async def choose_style(callback: types.CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")
    data = await state.get_data()
    face_image = data.get("face_image")
    prompt = data.get("prompt")

    if not prompt:
        await callback.message.answer("❌ Ошибка: промпт не найден. Начни заново.")
        await state.clear()
        return

    user_id = callback.from_user.id
    if not usage.increment(user_id):
        await callback.message.answer("❌ Дневной лимит исчерпан.")
        await state.clear()
        return

    await state.set_state(UserStates.generating)
    await callback.message.edit_text("⏳ Генерирую изображение через Cloudflare...")

    try:
        # Step 1: Generate image via Cloudflare
        image_bytes = await generate_with_cloudflare(prompt, style=style)
        if not image_bytes:
            raise Exception("Cloudflare did not return an image")

        # Step 2: If face image exists, perform face swap
        if face_image:
            await callback.message.edit_text("🔄 Выполняю замену лица на Hugging Face...")
            result_bytes = await facefusion_client.swap_face(face_image, image_bytes)
            caption = f"✅ Готово (с заменой лица)!\nПромпт: {prompt}\nСтиль: {style}"
        else:
            result_bytes = image_bytes
            caption = f"✅ Готово!\nПромпт: {prompt}\nСтиль: {style}"

        # Step 3: Send result
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=BufferedInputFile(result_bytes, filename="result.jpg"),
            caption=caption
        )
    except Exception as e:
        logger.exception("Generation error")
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
    finally:
        await state.clear()
        await callback.message.answer(
            "Что делаем дальше?",
            reply_markup=get_main_menu()
        )

# ------------------------------------------------------------
# Webhook lifecycle
# ------------------------------------------------------------
async def on_startup(bot: Bot):
    webhook_url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    # Send startup notification
    asyncio.create_task(send_startup_notification())

async def on_shutdown(bot: Bot):
    # await bot.delete_webhook()
    logger.info("Webhook removed")

def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info(f"Starting server on port {config.PORT}")
    web.run_app(app, host="0.0.0.0", port=config.PORT)

if __name__ == "__main__":
    main()
