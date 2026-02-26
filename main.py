#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Telegram Bot
Основной файл с обработчиками.
Поддерживает:
- Генерацию изображений через Cloudflare Workers AI
- Замену лица через FaceFusion API на Hugging Face
- Перевод промптов с русского на английский
- Загрузку лица как фото или документа
- Выбор пола для автоматического дополнения промпта
- Расширенный выбор стилей и возможность ввода своего стиля
- Цветные inline-кнопки (Telegram API 9.4+)
- Уведомление администратора о запуске
- Корректную обработку долгих запросов (без ошибок callback)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Union

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, Message, CallbackQuery
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config
from states import UserStates
from keyboards import get_main_menu, get_gender_keyboard, get_style_keyboard
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Клиенты внешних сервисов
facefusion_client = FaceFusionClient(api_url=config.FACEFUSION_URL)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# ------------------------------------------------------------
# Вспомогательные функции для унифицированной отправки сообщений
# ------------------------------------------------------------
async def send_message(
    event: Union[Message, CallbackQuery],
    text: str,
    reply_markup=None,
    parse_mode: str = "MarkdownV2"
) -> Message:
    """
    Отправляет сообщение, независимо от того, Message это или CallbackQuery.
    Для CallbackQuery не пытается ответить на callback, а просто шлёт новое сообщение.
    """
    if isinstance(event, CallbackQuery):
        return await event.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        return await event.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

async def send_photo(
    event: Union[Message, CallbackQuery],
    photo: BufferedInputFile,
    caption: str = "",
    parse_mode: str = "MarkdownV2"
) -> Message:
    """Отправляет фото, аналогично send_message."""
    if isinstance(event, CallbackQuery):
        return await event.message.answer_photo(photo=photo, caption=caption, parse_mode=parse_mode)
    else:
        return await event.answer_photo(photo=photo, caption=caption, parse_mode=parse_mode)

async def edit_message(
    event: Union[Message, CallbackQuery],
    text: str,
    reply_markup=None
) -> types.Message:
    """Редактирует сообщение, если это возможно (для CallbackQuery)."""
    if isinstance(event, CallbackQuery):
        return await event.message.edit_text(text, reply_markup=reply_markup)
    else:
        # Для обычного сообщения редактировать нельзя, просто ответим
        return await event.answer(text, reply_markup=reply_markup)

# ------------------------------------------------------------
# Уведомление администратора о запуске
# ------------------------------------------------------------
async def send_startup_notification():
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
# Команда /start
# ------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
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
# Обработчики главного меню
# ------------------------------------------------------------
@dp.message(lambda msg: msg.text == "🔄 С заменой лица")
async def create_photo_start(message: Message, state: FSMContext):
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
async def simple_generation_start(message: Message, state: FSMContext):
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
async def show_stats(message: Message):
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
async def help_cmd(message: Message):
    await message.answer(
        "📖 *Помощь*\n\n"
        "**🔄 С заменой лица:**\n"
        "1\\. Нажми кнопку «🔄 С заменой лица»\n"
        "2\\. Отправь фото с лицом \\(или файл\\-изображение\\)\n"
        "3\\. Выбери пол человека\n"
        "4\\. Напиши промпт \\(описание сцены\\)\n"
        "5\\. Выбери стиль или введи свой\n\n"
        "**✨ Просто генерация:**\n"
        "1\\. Нажми «✨ Просто генерация»\n"
        "2\\. Напиши промпт\n"
        "3\\. Выбери стиль или введи свой\n\n"
        f"Дневной лимит: {config.DAILY_LIMIT} генераций",
        parse_mode="MarkdownV2"
    )

@dp.message(lambda msg: msg.text == "ℹ️ О боте")
async def about_cmd(message: Message):
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
# Загрузка фото лица (фото или документ)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face, F.photo)
async def handle_face_photo(message: Message, state: FSMContext):
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
async def handle_face_document(message: Message, state: FSMContext):
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
async def handle_face_invalid(message: Message):
    await message.answer("Пожалуйста, отправь фотографию или файл с изображением.")

# ------------------------------------------------------------
# Выбор пола
# ------------------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await state.set_state(UserStates.waiting_for_prompt)
    await callback.message.edit_text(
        "✅ Пол учтён. Теперь напиши текстовое описание того, что должно быть на финальном изображении.\n"
        "Например: *в костюме на фоне космоса* (пол будет добавлен автоматически)"
    )

# ------------------------------------------------------------
# Обработка промпта (с лицом)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt)
async def handle_prompt(message: Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("Промпт не может быть пустым. Напиши описание.")
        return

    data = await state.get_data()
    gender = data.get("gender")
    gender_word = "мужчина" if gender == "male" else "женщина"
    if gender_word not in prompt.lower():
        prompt = f"{gender_word}, {prompt}"

    await state.update_data(prompt=prompt)
    await state.set_state(UserStates.choosing_style)
    await message.answer(
        "Выбери стиль для генерации или введи свой:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Обработка промпта (простая генерация, без лица)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_simple)
async def handle_simple_prompt(message: Message, state: FSMContext):
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
# Общая функция запуска генерации после выбора стиля
# ------------------------------------------------------------
async def proceed_to_generation(event: Union[Message, CallbackQuery], state: FSMContext):
    data = await state.get_data()
    face_image = data.get("face_image")
    prompt = data.get("prompt")
    chosen_style = data.get("chosen_style")

    # Проверка наличия необходимых данных
    if not prompt or not chosen_style:
        await send_message(
            event,
            "❌ Ошибка: не хватает данных для генерации. Начни заново."
        )
        await state.clear()
        return

    full_prompt = f"{prompt}, {chosen_style}"

    # Проверка лимита
    user_id = event.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return

    await state.set_state(UserStates.generating)

    # Отправляем сообщение о начале генерации
    status_msg = await send_message(event, "⏳ Генерирую изображение через Cloudflare...")

    try:
        # Генерация через Cloudflare (перевод промпта внутри функции)
        image_bytes = await generate_with_cloudflare(full_prompt)
        if not image_bytes:
            raise Exception("Cloudflare не вернул изображение")

        # Если есть лицо, выполняем замену
        if face_image:
            # Обновляем статус
            if isinstance(event, CallbackQuery):
                await event.message.edit_text("🔄 Выполняю замену лица на Hugging Face...")
            else:
                await status_msg.edit_text("🔄 Выполняю замену лица на Hugging Face...")

            result_bytes = await facefusion_client.swap_face(face_image, image_bytes)
            caption = f"✅ Готово (с заменой лица)!\nПромпт: {prompt}\nСтиль: {chosen_style}"
        else:
            result_bytes = image_bytes
            caption = f"✅ Готово!\nПромпт: {prompt}\nСтиль: {chosen_style}"

        # Удаляем статусное сообщение (если это callback, то редактируем его)
        if isinstance(event, CallbackQuery):
            await event.message.delete()
        else:
            await status_msg.delete()

        # Отправляем результат
        await send_photo(
            event,
            photo=BufferedInputFile(result_bytes, filename="result.jpg"),
            caption=caption
        )

    except Exception as e:
        logger.exception("Ошибка генерации")
        await send_message(event, f"❌ Ошибка: {str(e)}")

    finally:
        await state.clear()
        # Возвращаем главное меню
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# Выбор предустановленного стиля
# ------------------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("style_"))
async def choose_preset_style(callback: CallbackQuery, state: FSMContext):
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

# ------------------------------------------------------------
# Кнопка "Свой стиль"
# ------------------------------------------------------------
@dp.callback_query(lambda c: c.data == "custom_style")
async def custom_style_chosen(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_custom_style)
    await callback.message.edit_text(
        "✏️ Напиши свой стиль одним-двумя словами.\n"
        "Например: *киберпанк*, *барокко*, *фэнтези*, *минимализм* и т.д."
    )

@dp.message(UserStates.waiting_for_custom_style)
async def handle_custom_style(message: Message, state: FSMContext):
    custom_style = message.text.strip()
    if not custom_style:
        await message.answer("Стиль не может быть пустым. Попробуй ещё раз.")
        return
    await state.update_data(chosen_style=custom_style)
    await proceed_to_generation(message, state)

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
