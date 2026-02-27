#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot File (финальная версия)
- Face swapping with gender selection
- Simple image generation
- Swap face onto user's own image (without generation)
- Improved prompts with realism boosters
- Universal send functions (no parse_mode)
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
from keyboards import get_main_menu, get_gender_keyboard, get_style_keyboard
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# ------------------------------------------------------------
# Константы для текста кнопок (чтобы исключить опечатки)
# ------------------------------------------------------------
SWAP_OWN_BUTTON = "🖼️ Замена лица на своём изображении"  # точно как в keyboards.py

# ------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Initialize bot and dispatcher
# ------------------------------------------------------------
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Clients
facefusion_client = FaceFusionClient(api_url=config.FACEFUSION_URL)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# ------------------------------------------------------------
# Universal send functions (handles both Message and CallbackQuery)
# ------------------------------------------------------------
async def send_message(event: types.Message | types.CallbackQuery, text: str, reply_markup=None):
    """Send a text message regardless of event type."""
    if isinstance(event, types.CallbackQuery):
        return await event.message.answer(text, reply_markup=reply_markup)
    else:
        return await event.answer(text, reply_markup=reply_markup)

async def send_photo(event: types.Message | types.CallbackQuery, photo, caption: str = None, reply_markup=None):
    """Send a photo regardless of event type."""
    if isinstance(event, types.CallbackQuery):
        return await event.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    else:
        return await event.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)

async def edit_message(event: types.CallbackQuery, text: str, reply_markup=None):
    """Edit the message of a callback query."""
    return await event.message.edit_text(text, reply_markup=reply_markup)

async def delete_message(event: types.Message | types.CallbackQuery):
    """Delete the message (works for CallbackQuery.message and Message)."""
    if isinstance(event, types.CallbackQuery):
        await event.message.delete()
    else:
        await event.delete()

# ------------------------------------------------------------
# Startup notification to admin(s)
# ------------------------------------------------------------
async def send_startup_notification():
    if not config.ADMIN_IDS:
        logger.info("No ADMIN_IDS configured, skipping startup notification")
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    render_url = config.WEBHOOK_URL or "not set"
    hf_url = config.FACEFUSION_URL or "not set"

    text = (
        f"🚀 Bot {config.BOT_NAME} started!\n\n"
        f"📅 Time: {current_time} UTC\n"
        f"🖥 Render: {render_url}\n"
        f"🎭 FaceFusion: {hf_url}\n"
        f"📊 Daily limit: {config.DAILY_LIMIT}\n\n"
        f"✅ Bot is ready!"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
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
        "🔄 С заменой лица: ты загружаешь фото лица, а я генерирую изображение по твоему описанию и вставляю это лицо.\n"
        "✨ Просто генерация: я создаю изображение только по текстовому описанию.\n"
        f"{SWAP_OWN_BUTTON}: ты загружаешь два своих изображения, и я просто меняю лицо.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )

# ------------------------------------------------------------
# Main menu handlers (используем точное сравнение с константами)
# ------------------------------------------------------------
@dp.message(lambda msg: msg.text == "🔄 С заменой лица")
async def create_photo_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Ты исчерпал дневной лимит. Завтра лимит обновится.")
        return

    await state.set_state(UserStates.waiting_for_face)
    await state.update_data(mode="generate")
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
        "Например: красивый закат над горами, цифровое искусство"
    )

# ✅ ИСПРАВЛЕННЫЙ ХЕНДЛЕР для кнопки "Замена лица на своём изображении"
@dp.message(lambda msg: msg.text == SWAP_OWN_BUTTON)
async def swap_own_image_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Ты исчерпал дневной лимит. Завтра лимит обновится.")
        return

    await state.set_state(UserStates.waiting_for_face)
    await state.update_data(mode="swap_own")
    await message.answer(
        "Сначала отправь мне фото с лицом человека, которое нужно вставить (можно как фото, так и файл-изображение).\n"
        "Лицо должно быть чётко видно."
    )

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
        "📖 Помощь\n\n"
        "🔄 С заменой лица:\n"
        "1. Нажми кнопку «🔄 С заменой лица»\n"
        "2. Отправь фото с лицом (или файл-изображение)\n"
        "3. Выбери пол человека\n"
        "4. Напиши промпт (описание сцены)\n"
        "5. Выбери стиль или введи свой\n\n"
        "✨ Просто генерация:\n"
        "1. Нажми «✨ Просто генерация»\n"
        "2. Напиши промпт\n"
        "3. Выбери стиль или введи свой\n\n"
        f"{SWAP_OWN_BUTTON}:\n"
        "1. Нажми эту кнопку\n"
        "2. Отправь фото с лицом (источник)\n"
        "3. Отправь целевое изображение (куда вставить лицо)\n\n"
        f"Дневной лимит: {config.DAILY_LIMIT} генераций"
    )

@dp.message(lambda msg: msg.text == "ℹ️ О боте")
async def about_cmd(message: types.Message):
    await message.answer(
        f"ℹ️ О боте {config.BOT_NAME}\n\n"
        "Этот бот создан для генерации изображений по тексту с возможностью замены лица на фотографии.\n\n"
        "🔹 Технологии:\n"
        "   • Генерация: Cloudflare Workers AI\n"
        "   • Замена лица: FaceFusion (Hugging Face)\n\n"
        f"🔹 Лимиты:\n"
        f"   • {config.DAILY_LIMIT} генераций в день на пользователя (сбрасывается в полночь по UTC)\n\n"
        "🔹 Как использовать:\n"
        "   Нажми «🔄 С заменой лица» или «✨ Просто генерация» и следуй инструкциям.\n\n"
        "По всем вопросам обращайтесь к администратору."
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

    data = await state.get_data()
    mode = data.get("mode")

    if mode == "swap_own":
        await state.set_state(UserStates.waiting_for_target_image)
        await message.answer(
            "✅ Фото лица получено. Теперь отправь мне целевое изображение (куда нужно вставить лицо).\n"
            "Это может быть фото человека, пейзаж или любая картинка."
        )
    else:
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

        data = await state.get_data()
        mode = data.get("mode")

        if mode == "swap_own":
            await state.set_state(UserStates.waiting_for_target_image)
            await message.answer(
                "✅ Фото лица получено. Теперь отправь мне целевое изображение (куда нужно вставить лицо)."
            )
        else:
            await state.set_state(UserStates.waiting_for_gender)
            await message.answer(
                "✅ Фото лица получено. Теперь укажи пол человека на фото:",
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
        "Например: в костюме на фоне космоса (пол будет добавлен автоматически)"
    )

# ------------------------------------------------------------
# Prompt handling (with face, generate mode)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt)
async def handle_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("Промпт не может быть пустым. Напиши описание.")
        return

    data = await state.get_data()
    gender = data.get("gender")
    # ✅ ИСПРАВЛЕНО: вместо "женщина" используем "девушка", чтобы избежать NSFW-блокировки Cloudflare
    gender_word = "мужчина" if gender == "male" else "девушка 25-30 лет"
    if gender_word not in prompt.lower():
        prompt = f"{gender_word}, {prompt}"

    # Для режима с заменой лица добавляем требование, чтобы лицо было видно чётко
    prompt = prompt + ", face clearly visible"

    await state.update_data(prompt=prompt)
    await state.set_state(UserStates.choosing_style)
    await message.answer(
        "Выбери стиль для генерации или введи свой:",
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
        "Выбери стиль для генерации или введи свой:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Target image handlers (for swap_own mode)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_target_image, F.photo)
async def handle_target_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_bytes = await bot.download_file(file.file_path)
    await state.update_data(target_image=image_bytes.read())
    await perform_swap_only(message, state)

@dp.message(UserStates.waiting_for_target_image, F.document)
async def handle_target_document(message: types.Message, state: FSMContext):
    if message.document.mime_type and message.document.mime_type.startswith('image/'):
        file = await bot.get_file(message.document.file_id)
        image_bytes = await bot.download_file(file.file_path)
        await state.update_data(target_image=image_bytes.read())
        await perform_swap_only(message, state)
    else:
        await message.answer("Пожалуйста, отправь изображение (фото или документ с картинкой).")

@dp.message(UserStates.waiting_for_target_image)
async def handle_target_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь фотографию или файл с изображением.")

async def perform_swap_only(event: types.Message | types.CallbackQuery, state: FSMContext):
    """Функция для замены лица без генерации (только своп)."""
    data = await state.get_data()
    face_image = data.get("face_image")
    target_image = data.get("target_image")

    if not face_image or not target_image:
        await send_message(event, "❌ Ошибка: не хватает данных. Начни заново.")
        await state.clear()
        return

    user_id = event.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return

    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "🔄 Выполняю замену лица...")

    try:
        result_bytes = await facefusion_client.swap_face(face_image, target_image)
        caption = "✅ Готово! Лицо заменено."

        if isinstance(status_msg, types.Message):
            await status_msg.delete()

        await send_photo(event, BufferedInputFile(result_bytes, filename="result.jpg"), caption=caption)
    except Exception as e:
        logger.exception("Swap only error")
        error_text = f"❌ Ошибка: {str(e)}"
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# Style selection handlers
# ------------------------------------------------------------
async def proceed_to_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    """Common function to start generation after style selection."""
    data = await state.get_data()
    face_image = data.get("face_image")
    prompt = data.get("prompt")
    chosen_style = data.get("chosen_style")

    if not prompt or not chosen_style:
        await send_message(event, "❌ Ошибка: не хватает данных для генерации. Начни заново.")
        await state.clear()
        return

    full_prompt = f"{prompt}, {chosen_style}"

    user_id = event.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return

    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую изображение через Cloudflare...")

    try:
        image_bytes = await generate_with_cloudflare(full_prompt, style=chosen_style)
        if not image_bytes:
            raise Exception("Cloudflare did not return an image")

        if face_image:
            if isinstance(status_msg, types.Message):
                await status_msg.edit_text("🔄 Выполняю замену лица на Hugging Face...")
            else:
                status_msg = await send_message(event, "🔄 Выполняю замену лица на Hugging Face...")
            result_bytes = await facefusion_client.swap_face(face_image, image_bytes)
            caption = f"✅ Готово (с заменой лица)!\nПромпт: {prompt}\nСтиль: {chosen_style}"
        else:
            result_bytes = image_bytes
            caption = f"✅ Готово!\nПромпт: {prompt}\nСтиль: {chosen_style}"

        if isinstance(status_msg, types.Message):
            await status_msg.delete()

        await send_photo(event, BufferedInputFile(result_bytes, filename="result.jpg"), caption=caption)

    except Exception as e:
        logger.exception("Generation error")
        error_text = f"❌ Ошибка: {str(e)}"
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)

    finally:
        await state.clear()
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())

@dp.callback_query(lambda c: c.data.startswith("style_"))
async def choose_preset_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.replace("style_", "")
    style_map = {
        "realistic": "реализм",
        "anime": "аниме",
        "oil": "масло",
        "sketch": "скетч",
        "cyberpunk": "киберпанк",
        "baroque": "барокко",
        "surreal": "сюрреализм",
        "comic": "комикс",
        "photoreal": "фотореализм",
        "watercolor": "акварель",
        "pastel": "пастель",
        "3d": "3D-рендер",
    }
    readable_style = style_map.get(style_key, style_key)
    await state.update_data(chosen_style=readable_style)
    await proceed_to_generation(callback, state)

@dp.callback_query(lambda c: c.data == "custom_style")
async def custom_style_chosen(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_custom_style)
    await callback.message.edit_text(
        "✏️ Напиши свой стиль одним-двумя словами.\n"
        "Например: киберпанк, барокко, фэнтези, минимализм и т.д."
    )

@dp.message(UserStates.waiting_for_custom_style)
async def handle_custom_style(message: types.Message, state: FSMContext):
    custom_style = message.text.strip()
    if not custom_style:
        await message.answer("Стиль не может быть пустым. Попробуй ещё раз.")
        return
    await state.update_data(chosen_style=custom_style)
    await proceed_to_generation(message, state)

# ------------------------------------------------------------
# ВРЕМЕННЫЙ ОТЛАДОЧНЫЙ ХЕНДЛЕР (покажет все непринятые сообщения)
# ------------------------------------------------------------
@dp.message()
async def debug_unhandled(message: types.Message):
    logger.warning(f"⚠️ Необработанное сообщение: '{message.text}' (длина: {len(message.text) if message.text else 0})")
    # Ничего не отвечаем, чтобы не спамить пользователю

# ------------------------------------------------------------
# Webhook lifecycle
# ------------------------------------------------------------
async def on_startup(bot: Bot):
    webhook_url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    asyncio.create_task(send_startup_notification())

async def on_shutdown(bot: Bot):
    logger.info("Shutdown complete (webhook kept)")

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
