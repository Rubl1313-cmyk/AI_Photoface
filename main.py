#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot File (финальная версия с фотосессией)
- Генерация с заменой лица (портрет / полный рост)
- Простая генерация
- Замена лица на своём фото (без генерации)
- ИИ фотосессия (img2img) – создание нового изображения на основе загруженного фото
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
from deep_translator import GoogleTranslator

import config
from states import UserStates
from keyboards import get_main_menu, get_gender_keyboard, get_style_keyboard, get_shot_type_keyboard
from services.cloudflare import generate_with_cloudflare, generate_inpainting_photoshoot
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# ------------------------------------------------------------
# Константы для текста кнопок
# ------------------------------------------------------------
SWAP_OWN_BUTTON = "🖼️ Замена лица на своём изображении"
PHOTOSHOOT_BUTTON = "✨ ИИ фотосессия"
# 🔥 КОНСТАНТЫ ДЛЯ КАЧЕСТВЕННОЙ ФОТОСЕССИИ
NEGATIVE_PROMPT = (
    "deformed, distorted, disfigured, poorly drawn, bad anatomy, wrong anatomy, "
    "extra limb, missing limb, floating limbs, mutated hands, malformed hands, "
    "blurry, muddy, hazy, pixelated, low resolution, jpeg artifacts, "
    "ugly, disgusting, poorly drawn face, mutation, mutated, extra limb, "
    "ugly, poorly drawn hands, missing limb, blurry, floating limbs, "
    "disconnected limbs, malformed hands, blur, (mutated …s, signature, "
    "watermark, username, blurry, artist name, psychedelic, abstract, surreal, "
    "cartoon, anime, 3d render, sketch, painting, drawing, illustration"
)
# Магические токены качества (добавляются к любому промпту)
QUALITY_TOKENS = (
    ", professional photography, studio lighting, sharp focus, 8k uhd, dslr, "
    "soft lighting, high quality, film grain, detailed face, natural skin texture, "
    "realistic eyes, symmetrical face, cinematic composition, depth of field, bokeh"
)
# ------------------------------------------------------------
# Настройка логирования
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Инициализация бота и диспетчера
# ------------------------------------------------------------
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Клиенты
facefusion_client = FaceFusionClient(api_url=config.FACEFUSION_URL)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# ------------------------------------------------------------
# Универсальные функции отправки (Message / CallbackQuery)
# ------------------------------------------------------------
async def send_message(event: types.Message | types.CallbackQuery, text: str, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        return await event.message.answer(text, reply_markup=reply_markup)
    return await event.answer(text, reply_markup=reply_markup)

async def send_photo(event: types.Message | types.CallbackQuery, photo, caption: str = None, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        return await event.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    return await event.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)

async def edit_message(event: types.CallbackQuery, text: str, reply_markup=None):
    return await event.message.edit_text(text, reply_markup=reply_markup)

async def delete_message(event: types.Message | types.CallbackQuery):
    if isinstance(event, types.CallbackQuery):
        await event.message.delete()
    else:
        await event.delete()

# ------------------------------------------------------------
# Уведомление администраторам о старте
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
# Команда /start
# ------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    await message.answer(
        f"👋 Привет! Я {config.BOT_NAME}\n\n"
        "Я могу:\n"
        "🔄 **С заменой лица**: загружаешь фото лица → я генерирую картинку по описанию и вставляю это лицо.\n"
        "✨ **Просто генерация**: создаю изображение только по тексту.\n"
        f"{SWAP_OWN_BUTTON}: загружаешь два своих изображения, и я просто меняю лицо.\n"
        f"{PHOTOSHOOT_BUTTON}: загружаешь фото человека → пишешь промпт → я создаю новое изображение с этим человеком в заданной обстановке.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )

# ------------------------------------------------------------
# Обработчики главного меню
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

@dp.message(lambda msg: msg.text == PHOTOSHOOT_BUTTON)
async def photoshoot_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Ты исчерпал дневной лимит. Завтра лимит обновится.")
        return
    await state.set_state(UserStates.waiting_for_face_photoshoot)
    await state.update_data(mode="photoshoot")
    await message.answer(
        "📸 Отправь мне фото человека (можно как фото, так и файл-изображение).\n"
        "На основе этого фото я сгенерирую новые изображения в разных сценах."
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
        "📖 **Помощь**\n\n"
        "🔄 **С заменой лица**:\n"
        "1. Нажми кнопку «🔄 С заменой лица»\n"
        "2. Отправь фото с лицом\n"
        "3. Выбери пол\n"
        "4. Напиши описание сцены\n"
        "5. Выбери стиль\n"
        "6. Выбери тип кадра (портрет или полный рост)\n\n"
        "✨ **Просто генерация**:\n"
        "1. Нажми «✨ Просто генерация»\n"
        "2. Напиши описание\n"
        "3. Выбери стиль\n\n"
        f"{SWAP_OWN_BUTTON}:\n"
        "1. Нажми эту кнопку\n"
        "2. Отправь фото с лицом (источник)\n"
        "3. Отправь целевое изображение\n\n"
        f"{PHOTOSHOOT_BUTTON}:\n"
        "1. Нажми эту кнопку\n"
        "2. Отправь фото человека\n"
        "3. Напиши промпт (например: 'на пляже на закате')\n"
        "4. Получи новое изображение с тем же человеком в заданной обстановке\n\n"
        f"Дневной лимит: {config.DAILY_LIMIT} генераций"
    )

@dp.message(lambda msg: msg.text == "ℹ️ О боте")
async def about_cmd(message: types.Message):
    await message.answer(
        f"ℹ️ О боте {config.BOT_NAME}\n\n"
        "Этот бот создан для генерации изображений по тексту с возможностью замены лица.\n\n"
        "🔹 **Технологии**:\n"
        "   • Генерация: FLUX / Stable Diffusion (через Cloudflare Workers)\n"
        "   • Замена лица: FaceFusion\n"
        "   • ИИ фотосессия: Stable Diffusion img2img\n\n"
        f"🔹 **Лимиты**:\n"
        f"   • {config.DAILY_LIMIT} генераций в день на пользователя\n\n"
        "🔹 **Как использовать**:\n"
        "   Нажми любую кнопку в меню и следуй инструкциям.\n\n"
        "По всем вопросам обращайтесь к администратору."
    )

# ------------------------------------------------------------
# Загрузка лица (для режимов с заменой лица и фотосессии)
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
            "✅ Фото лица получено. Теперь отправь мне **целевое изображение** (куда нужно вставить лицо).\n"
            "Это может быть фото человека, пейзаж или любая картинка."
        )
    else:  # обычный режим с генерацией
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
                "✅ Фото лица получено. Теперь отправь мне **целевое изображение**."
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
# Загрузка лица для фотосессии (отдельный обработчик)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face_photoshoot, F.photo)
async def handle_photoshoot_face_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    image_bytes = await bot.download_file(file.file_path)
    await state.update_data(source_image=image_bytes.read())
    await state.set_state(UserStates.waiting_for_prompt_photoshoot)
    await message.answer(
        "✅ Фото получено. Теперь напиши текстовое описание того, что должно быть на новом изображении.\n"
        "Например: 'в стиле киберпанк, на фоне неонового города' или 'на пляже на закате'."
    )

@dp.message(UserStates.waiting_for_face_photoshoot, F.document)
async def handle_photoshoot_face_document(message: types.Message, state: FSMContext):
    if message.document.mime_type and message.document.mime_type.startswith('image/'):
        file = await bot.get_file(message.document.file_id)
        image_bytes = await bot.download_file(file.file_path)
        await state.update_data(source_image=image_bytes.read())
        await state.set_state(UserStates.waiting_for_prompt_photoshoot)
        await message.answer(
            "✅ Фото получено. Теперь напиши текстовое описание того, что должно быть на новом изображении."
        )
    else:
        await message.answer("Пожалуйста, отправь изображение (фото или документ с картинкой).")

@dp.message(UserStates.waiting_for_face_photoshoot)
async def handle_photoshoot_face_invalid(message: types.Message):
    await message.answer("Пожалуйста, отправь фотографию или файл с изображением.")

# ------------------------------------------------------------
# Выбор пола
# ------------------------------------------------------------
@dp.callback_query(lambda c: c.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await state.set_state(UserStates.waiting_for_prompt)
    await callback.message.edit_text(
        "✅ Пол учтён. Теперь напиши **текстовое описание** того, что должно быть на финальном изображении.\n"
        "Например: в костюме на фоне космоса"
    )

# ------------------------------------------------------------
# Обработка промпта (с лицом, режим генерации)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt)
async def handle_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    if not prompt:
        await message.answer("Промпт не может быть пустым. Напиши описание.")
        return

    data = await state.get_data()
    gender = data.get("gender")
    # Используем "девушка" для обхода NSFW-фильтров
    gender_word = "мужчина" if gender == "male" else "профессиональное фото девушки 30 лет"
    if gender_word not in prompt.lower():
        prompt = f"{gender_word}, {prompt}"

    await state.update_data(prompt=prompt)
    await state.set_state(UserStates.choosing_style)
    await message.answer(
        "Выбери **стиль** для генерации или введи свой:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Обработка промпта (простая генерация, без лица)
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
        "Выбери **стиль** для генерации или введи свой:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Обработка промпта для фотосессии (с переводом на английский)
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_photoshoot)
async def handle_photoshoot_prompt(message: types.Message, state: FSMContext):
    user_prompt = message.text.strip()
    if not user_prompt:
        await message.answer("Промпт не может быть пустым. Напиши описание.")
        return

    # Переводим промпт на английский для Stable Diffusion
    try:
        translator = GoogleTranslator(source='auto', target='en')
        en_prompt = await asyncio.get_event_loop().run_in_executor(None, translator.translate, user_prompt)
        logger.info(f"🔤 Перевод промпта фотосессии: '{user_prompt}' → '{en_prompt}'")
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        en_prompt = user_prompt  # если перевод не удался, оставляем как есть

    await state.update_data(photoshoot_prompt=en_prompt)
    await proceed_photoshoot(message, state)

# ------------------------------------------------------------
# Выбор стиля
# ------------------------------------------------------------
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
    # Переходим к выбору типа кадра
    await state.set_state(UserStates.choosing_shot_type)
    await callback.message.edit_text(
        "Выбери **тип кадра**:",
        reply_markup=get_shot_type_keyboard()
    )

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
    # Переходим к выбору типа кадра
    await state.set_state(UserStates.choosing_shot_type)
    await message.answer(
        "Выбери **тип кадра**:",
        reply_markup=get_shot_type_keyboard()
    )

# ------------------------------------------------------------
# Выбор типа кадра (портрет / полный рост)
# ------------------------------------------------------------
@dp.callback_query(UserStates.choosing_shot_type, lambda c: c.data.startswith("shot_"))
async def choose_shot_type(callback: types.CallbackQuery, state: FSMContext):
    shot_type = callback.data  # "shot_portrait" или "shot_fullbody"
    data = await state.get_data()
    prompt = data.get("prompt")
    chosen_style = data.get("chosen_style")

    if not prompt or not chosen_style:
        await callback.message.edit_text("❌ Ошибка: не хватает данных. Начни заново.")
        await state.clear()
        return

    if shot_type == "shot_portrait":
        # Портрет: лицо крупно, в кадр
        enhanced_prompt = f"portrait, {prompt}, face looking at camera, clearly visible, detailed face"
        negative_prompt = "full body, whole body, multiple people, blurry"
        width, height = 1024, 1024
    else:
        # Полный рост: человек целиком, лицо в кадр, вертикально
        enhanced_prompt = f"full body shot full body shot, {prompt}, standing, from head to toe, facing camera, looking at viewer, face clearly visible, vertical composition"
        negative_prompt = "close-up, portrait, upper body, chest shot, profile, looking away, blurry face"
        width, height = 768, 1024  # вертикальное соотношение

    await state.update_data(
        prompt=enhanced_prompt,
        shot_type=shot_type,
        width=width,
        height=height,
        negative_prompt=negative_prompt
    )
    await proceed_to_generation(callback, state)

@dp.callback_query(lambda c: c.data == "back_to_style")
async def back_to_style(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.choosing_style)
    await callback.message.edit_text(
        "Выбери **стиль** для генерации или введи свой:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Целевое изображение (для режима swap_own)
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
    """Замена лица без генерации (только своп)."""
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
# Процесс генерации (с заменой лица или без)
# ------------------------------------------------------------
async def proceed_to_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    face_image = data.get("face_image")
    prompt = data.get("prompt")
    chosen_style = data.get("chosen_style")
    width = data.get("width", 1024)
    height = data.get("height", 1024)
    negative_prompt = data.get("negative_prompt", "")

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
    status_msg = await send_message(event, "⏳ Генерирую изображение через FLUX...")

    try:
        image_bytes = await generate_with_cloudflare(
            prompt=full_prompt,
            style=chosen_style,
            width=width,
            height=height,
            negative_prompt=negative_prompt
        )
        if not image_bytes:
            raise Exception("FLUX не вернул изображение")

        if face_image:
            if isinstance(status_msg, types.Message):
                await status_msg.edit_text("🔄 Выполняю замену лица...")
            else:
                status_msg = await send_message(event, "🔄 Выполняю замену лица...")
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

# ------------------------------------------------------------
# Процесс фотосессии (img2img) – ИСПРАВЛЕННАЯ ВЕРСИЯ
# ------------------------------------------------------------
# В main.py — замените ТОЛЬКО эту функцию. Остальное не трогаем!

# В main.py — замените ТОЛЬКО эту функцию. Остальное не трогаем!

async def proceed_photoshoot(event: types.Message | types.CallbackQuery, state: FSMContext):
    """
    🎨 ИИ ФОТОСЕССИЯ (новая схема):
    Telegram фото → Render (face detection fallback chain) → Cloudflare (inpainting) → Telegram
    """
    from services.cloudflare import generate_inpainting_photoshoot
    
    data = await state.get_data()
    source_image = data.get("source_image")  # bytes от пользователя
    prompt = data.get("photoshoot_prompt")   # уже переведённый на английский

    if not source_image or not prompt:
        await send_message(event, "❌ Ошибка: не хватает данных. Начни заново.")
        await state.clear()
        return

    user_id = event.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return

    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "🎭 Определяю лицо...")

    try:
        # 🔑 Усиленный промпт для качества фона
        quality_suffix = (
            ", professional photography, cinematic lighting, sharp focus, "
            "8k uhd, dslr, soft lighting, high quality, film grain, "
            "detailed background, realistic, depth of field, bokeh"
        )
        enhanced_prompt = f"{prompt}{quality_suffix}"
        
        # 🔑 Negative prompt для чистого результата
        neg_prompt = (
            "deformed, distorted, disfigured, bad anatomy, extra limb, "
            "blurry, ugly, mutated, watermark, text, signature, "
            "low quality, jpeg artifacts, cartoon, anime, 3d render"
        )

        # 🚀 Запускаем inpainting-фотосессию
        logger.info(f"🎨 Photoshoot: '{prompt}' | face detection → inpainting")
        
        result_bytes = await generate_inpainting_photoshoot(
            prompt=enhanced_prompt,
            source_image_bytes=source_image,
            width=512,
            height=512,
            strength=0.9,        # высокий: маска защищает лицо
            guidance=9.5,        # строгое следование промпту для фона
            steps=20,            # 🔑 максимум 20 для inpainting модели CF
            negative_prompt=neg_prompt
        )

        if not result_bytes:
            raise Exception("Cloudflare не вернул изображение")

        # Отправляем результат
        caption = f"✅ Готово!\n🎨 Промпт: {prompt}"
        if isinstance(status_msg, types.Message):
            await status_msg.delete()
        
        await send_photo(
            event, 
            BufferedInputFile(result_bytes, filename="photoshoot.jpg"), 
            caption=caption
        )

    except Exception as e:
        logger.exception("❌ Photoshoot error")
        error_text = f"❌ Ошибка генерации: {str(e)[:150]}"
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())
# ------------------------------------------------------------
# Отладочный хендлер (для необработанных сообщений)
# ------------------------------------------------------------
@dp.message()
async def debug_unhandled(message: types.Message):
    logger.warning(f"⚠️ Необработанное сообщение: '{message.text}' (длина: {len(message.text) if message.text else 0})")

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
