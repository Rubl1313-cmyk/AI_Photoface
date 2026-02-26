#!/usr/bin/env python3
"""🎨 AI PhotoStudio — Render.com (Webhook)"""

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config
from states import UserStates
from keyboards import get_main_menu, get_style_keyboard
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Клиент для FaceFusion API
facefusion_client = FaceFusionClient(api_url=config.FACEFUSION_URL)

# Трекер лимитов
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# Временное хранилище для данных пользователя (в реальном проекте лучше использовать FSM storage)
user_data = {}

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    await message.answer(
        f"👋 Привет! Я {config.BOT_NAME}\n\n"
        "Я могу:\n"
        "1️⃣ Создавать изображения по тексту (через Cloudflare AI)\n"
        "2️⃣ Заменять лицо на фото (через FaceFusion на Hugging Face)\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )

@dp.message(lambda msg: msg.text == "🎨 Создать фото")
async def create_photo_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Ты исчерпал дневной лимит (50 генераций). Завтра лимит обновится.")
        return
    await state.set_state(UserStates.waiting_for_face)
    await message.answer(
        "Отправь мне фото с лицом человека, которое нужно вставить.\n"
        "(можно одно фото, лицо должно быть чётко видно)"
    )

@dp.message(UserStates.waiting_for_face, F.photo)
async def handle_face_photo(message: types.Message, state: FSMContext, album: list = None):
    # Если пришёл альбом, берём первую фотку
    photo = message.photo[-1] if not album else album[0].photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = file.file_path
    # Скачиваем во временную память
    image_bytes = await bot.download_file(file_path)
    # Сохраняем байты в FSM data
    await state.update_data(face_image=image_bytes.read())
    await state.set_state(UserStates.waiting_for_prompt)
    await message.answer(
        "✅ Фото лица получено. Теперь напиши текстовое описание того, что должно быть на финальном изображении.\n"
        "Например: *мужчина в костюме на фоне космоса*",
        parse_mode="Markdown"
    )

@dp.message(UserStates.waiting_for_face)
async def handle_no_photo(message: types.Message):
    await message.answer("Пожалуйста, отправь фотографию с лицом.")

@dp.message(UserStates.waiting_for_prompt)
async def handle_prompt(message: types.Message, state: FSMContext):
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

@dp.callback_query(lambda c: c.data.startswith("style_"))
async def choose_style(callback: types.CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")
    data = await state.get_data()
    face_image = data.get("face_image")
    prompt = data.get("prompt")
    if not face_image or not prompt:
        await callback.message.answer("❌ Ошибка: данные не найдены. Начни заново.")
        await state.clear()
        return

    # Учитываем использование
    user_id = callback.from_user.id
    if not usage.increment(user_id):
        await callback.message.answer("❌ Дневной лимит исчерпан.")
        await state.clear()
        return

    await state.set_state(UserStates.generating)
    await callback.message.edit_text("⏳ Генерирую изображение через Cloudflare...")

    try:
        # 1. Генерация изображения по промпту через Cloudflare
        image_bytes = await generate_with_cloudflare(prompt, style=style)
        if not image_bytes:
            raise Exception("Cloudflare не вернул изображение")

        # 2. Замена лица через FaceFusion на Hugging Face
        await callback.message.edit_text("🔄 Выполняю замену лица на Hugging Face...")
        swapped_bytes = await facefusion_client.swap_face(face_image, image_bytes)

        # 3. Отправляем результат
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=BufferedInputFile(swapped_bytes, filename="result.jpg"),
            caption=f"✅ Готово!\nПромпт: {prompt}\nСтиль: {style}"
        )
    except Exception as e:
        logger.exception("Ошибка генерации")
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
    finally:
        await state.clear()
        await callback.message.answer("Что делаем дальше?", reply_markup=get_main_menu())

@dp.message(Command("stats"))
@dp.message(lambda msg: msg.text == "📊 Моя статистика")
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    used = usage.get_usage(user_id)
    left = max(0, config.DAILY_LIMIT - used)
    await message.answer(
        f"📊 Статистика:\n"
        f"Использовано сегодня: {used} из {config.DAILY_LIMIT}\n"
        f"Осталось: {left}"
    )

@dp.message(lambda msg: msg.text == "❓ Помощь")
async def help_cmd(message: types.Message):
    await message.answer(
        "📖 *Помощь*\n\n"
        "1. Нажми «🎨 Создать фото»\n"
        "2. Отправь фото с лицом\n"
        "3. Напиши промпт (описание)\n"
        "4. Выбери стиль\n"
        "5. Жди результат (около 30–60 сек)\n\n"
        "Бот использует Cloudflare Workers AI для генерации и FaceFusion (Hugging Face) для замены лица.",
        parse_mode="Markdown"
    )

# Webhook setup
async def on_startup(bot: Bot):
    await bot.set_webhook(f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()

def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    # Запуск aiohttp сервера
    web.run_app(app, host="0.0.0.0", port=config.PORT)

if __name__ == "__main__":
    main()
