#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot File (COMPLETE & FIXED)
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

DEFAULT_REALISTIC_PROMPT = (
    "professional photography, photorealistic, sharp focus, 8k uhd, "
    "dslr, soft lighting, high quality, film grain, natural skin texture, "
    "realistic details, depth of field, bokeh, studio lighting"
)

STYLE_PROMPTS = {
    "style_photorealistic": "photorealistic, professional photography",
    "style_hyperrealistic": "hyperrealistic, ultra detailed, 8k resolution",
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
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# ------------------------------------------------------------
# Универсальные функции
# ------------------------------------------------------------
# ... (все импорты и константы как раньше) ...

# ------------------------------------------------------------
# Универсальные функции — 🔥 ИСПРАВЛЕНО!
# ------------------------------------------------------------
async def send_message(event: types.Message | types.CallbackQuery, text: str, reply_markup=None):
    """Отправляет сообщение, корректно обрабатывая Message и CallbackQuery"""
    if isinstance(event, types.CallbackQuery):
        await event.answer()  # Убираем "loading" у callback
        return await event.message.answer(text, reply_markup=reply_markup)
    else:
        # 🔥 ИСПРАВЛЕНО: используем reply() вместо несуществующего answer()
        return await event.reply(text, reply_markup=reply_markup)

async def send_photo(event: types.Message | types.CallbackQuery, photo, caption: str = None, reply_markup=None):
    if caption:
        caption = truncate_caption(caption, max_length=MAX_CAPTION_LENGTH)
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        return await event.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    else:
        return await event.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup)

async def edit_message(event: types.CallbackQuery, text: str, reply_markup=None):
    return await event.message.edit_text(text, reply_markup=reply_markup)

def validate_prompt_length(prompt: str, max_length: int = MAX_PROMPT_LENGTH) -> tuple[bool, str]:
    if not prompt or len(prompt.strip()) == 0:
        return False, "❌ Промпт не может быть пустым."
    if len(prompt) > max_length:
        return False, f"❌ Промпт слишком длинный (максимум {max_length} символов)."
    return True, ""

# ------------------------------------------------------------
# /start
# ------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    await message.answer(
        f"👋 Привет! Я {config.BOT_NAME}\n\n"
        "🔄 **С заменой лица**: фото → генерация → твоё лицо\n"
        "✨ **Просто генерация**: изображение по тексту\n"
        f"{SWAP_OWN_BUTTON}: меняю лицо на твоём фото\n"
        f"{PHOTOSHOOT_BUTTON}: фотосессия с твоим лицом\n\n"
        "📝 Промпт максимум 1024 символа.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )

# ------------------------------------------------------------
# 🔘 ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ (CALLBACK)
# ------------------------------------------------------------

@dp.callback_query(lambda c: c.data == "mode_generate")
async def create_photo_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not usage.check_limit(user_id):
        await callback.answer("❌ Дневной лимит исчерпан.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(UserStates.waiting_for_face)
    await state.update_data(mode="generate")
    await callback.message.answer(
        "📸 Отправь фото с лицом (анфас, хорошее освещение).\n"
        "📝 Чем лучше фото, тем качественнее результат!"
    )
    logger.info(f"🔄 Mode generate started by user {user_id}")


@dp.callback_query(lambda c: c.data == "mode_simple")
async def simple_generation_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not usage.check_limit(user_id):
        await callback.answer("❌ Дневной лимит исчерпан.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(UserStates.waiting_for_prompt_simple)
    await callback.message.answer(
        "✨ Напиши описание что сгенерировать.\n"
        "📝 Максимум 1024 символа.\n"
        "💡 Пример: красивый закат над горами, цифровое искусство"
    )
    logger.info(f"✨ Mode simple started by user {user_id}")


@dp.callback_query(lambda c: c.data == "mode_swap_own")
async def swap_own_image_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not usage.check_limit(user_id):
        await callback.answer("❌ Дневной лимит исчерпан.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(UserStates.waiting_for_face)
    await state.update_data(mode="swap_own")
    await callback.message.answer(
        "🖼️ Отправь фото лица которое нужно вставить.\n"
        "После этого отправь фото НА которое заменить."
    )
    logger.info(f"🖼️ Mode swap_own started by user {user_id}")


@dp.callback_query(lambda c: c.data == "mode_photoshoot")
async def photoshoot_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not usage.check_limit(user_id):
        await callback.answer("❌ Дневной лимит исчерпан.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(UserStates.waiting_for_face_photoshoot)
    await state.update_data(mode="photoshoot")
    await callback.message.answer(
        "🎨 Отправь фото человека для фотосессии.\n"
        "📝 Лицо должно быть чётко видно, анфас."
    )
    logger.info(f"🎨 Mode photoshoot started by user {user_id}")


@dp.callback_query(lambda c: c.data == "stats")
async def process_stats(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    remaining = config.DAILY_LIMIT - len(usage.usage.get(user_id, []))
    used = config.DAILY_LIMIT - remaining
    await callback.message.answer(
        f"📊 **Ваша статистика**\n\n"
        f"🔹 Использовано сегодня: {used}/{config.DAILY_LIMIT}\n"
        f"🔹 Осталось: {remaining}\n"
        f"🔹 Лимит обновится: завтра в 00:00 UTC",
        reply_markup=get_main_menu()
    )
    logger.info(f"📊 Stats requested by user {user_id}: {used}/{config.DAILY_LIMIT}")


@dp.callback_query(lambda c: c.data == "help")
async def process_help(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        f"❓ **Помощь — {config.BOT_NAME}**\n\n"
        f"🔄 **С заменой лица**:\n"
        f"   1. Отправь фото лица\n"
        f"   2. Выбери пол → стиль → тип кадра\n"
        f"   3. Напиши промпт\n"
        f"   4. Получи результат!\n\n"
        f"✨ **Просто генерация**:\n"
        f"   Напиши промпт → получи изображение\n\n"
        f"🖼️ **Замена на своём фото**:\n"
        f"   Отправь 2 фото → заменю лицо\n\n"
        f"🎨 **ИИ фотосессия**:\n"
        f"   Отправь фото + промпт → фотосессия\n\n"
        f"📝 Промпт максимум 1024 символа.",
        reply_markup=get_main_menu()
    )
    logger.info(f"❓ Help requested by user {callback.from_user.id}")

# ------------------------------------------------------------
# Получение фото
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face, F.photo | F.document)
async def receive_face_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document and message.document.mime_type.startswith("image/"):
            photo = message.document
        if not photo:
            await message.answer("❌ Это не изображение."); return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        source_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        data = await state.get_data()
        if data.get("mode") == "generate":
            await state.update_data(face_image=source_image)
            await state.set_state(UserStates.waiting_for_gender)
            await message.answer("Выберите пол:", reply_markup=get_gender_keyboard())
        elif data.get("mode") == "swap_own":
            await state.update_data(source_face=source_image)
            await state.set_state(UserStates.waiting_for_target_swap)
            await message.answer("Теперь отправь фото НА которое заменить лицо.")
    except Exception as e:
        logger.exception("Error receiving face photo")
        await message.answer(f"❌ Ошибка: {str(e)}"); await state.clear()

@dp.message(UserStates.waiting_for_face_photoshoot, F.photo | F.document)
async def receive_photoshoot_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document and message.document.mime_type.startswith("image/"):
            photo = message.document
        if not photo:
            await message.answer("❌ Это не изображение."); return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        source_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        await state.update_data(source_image=source_image)
        await state.set_state(UserStates.waiting_for_gender_photoshoot)
        await message.answer("🎨 Выберите пол для фотосессии:", reply_markup=get_gender_keyboard())
    except Exception as e:
        logger.exception("Error receiving photoshoot photo")
        await message.answer(f"❌ Ошибка: {str(e)}"); await state.clear()

# ------------------------------------------------------------
# Выбор пола
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_gender, lambda c: c.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await state.set_state(UserStates.waiting_for_style)
    logger.info(f"👤 Gender: {gender}")
    await callback.message.edit_text("✅ Пол учтён. Выберите стиль:", reply_markup=get_style_keyboard())

@dp.callback_query(UserStates.waiting_for_gender_photoshoot, lambda c: c.data.startswith("gender_"))
async def process_gender_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await state.set_state(UserStates.waiting_for_shot_type_photoshoot)
    logger.info(f"👤 Photoshoot gender: {gender}")
    await callback.message.edit_text("✅ Пол учтён. Выберите тип кадра:", reply_markup=get_shot_type_keyboard())

# ------------------------------------------------------------
# Выбор стиля
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_style, lambda c: c.data.startswith("style_"))
async def process_style(callback: types.CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")
    await state.update_data(chosen_style=style)
    await state.set_state(UserStates.waiting_for_shot_type)
    logger.info(f"🎨 Style: {style}")
    await callback.message.edit_text("✅ Стиль выбран. Выберите тип кадра:", reply_markup=get_shot_type_keyboard())

# ------------------------------------------------------------
# Выбор типа кадра
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_shot_type, lambda c: c.data.startswith("shot_"))
async def process_shot_type(callback: types.CallbackQuery, state: FSMContext):
    shot_type = callback.data.replace("shot_", "")
    await state.update_data(shot_type=shot_type)
    await state.set_state(UserStates.waiting_for_prompt)
    shot_text = "портрет" if shot_type == "portrait" else "в полный рост"
    await callback.message.edit_text(f"✅ {shot_text}. Напишите описание сцены:\n📝 Максимум 1024 символа.")

@dp.callback_query(UserStates.waiting_for_shot_type_photoshoot, lambda c: c.data.startswith("shot_"))
async def process_shot_type_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    shot_type = callback.data.replace("shot_", "")
    await state.update_data(shot_type=shot_type)
    await state.set_state(UserStates.waiting_for_prompt_photoshoot)
    shot_text = "портрет" if shot_type == "portrait" else "в полный рост"
    await callback.message.edit_text(f"✅ {shot_text}. Опишите сцену:\n📝 Максимум 1024 символа.\n🔥 Реализм добавлю автоматически.")

# ------------------------------------------------------------
# Промпты
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt, F.text)
async def receive_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg); return
    await proceed_to_generation(message, state)

@dp.message(UserStates.waiting_for_prompt_simple, F.text)
async def receive_prompt_simple(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg); return
    await proceed_simple_generation(message, state)

@dp.message(UserStates.waiting_for_prompt_photoshoot, F.text)
async def receive_prompt_photoshoot(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg); return
    await proceed_photoshoot(message, state)

# ------------------------------------------------------------
# 🔥 Генерация с заменой лица
# ------------------------------------------------------------
async def proceed_to_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    source_face = data.get("face_image")
    gender = data.get("gender")
    style = data.get("chosen_style")
    shot_type = data.get("shot_type")
    prompt = event.text.strip() if isinstance(event, types.Message) else data.get("prompt")
    
    if not source_face or not prompt:
        await send_message(event, "❌ Ошибка данных."); await state.clear(); return
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg); await state.clear(); return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Лимит исчерпан."); await state.clear(); return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую... ~60-90 сек")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(prompt)
        gender_text = "man" if gender == "male" else "woman"
        shot_text = "portrait, close-up" if shot_type == "portrait" else "full body shot"
        style_text = STYLE_PROMPTS.get(style, "")
        
        full_prompt = f"{translated}, {gender_text}, {shot_text}, {style_text}, {DEFAULT_REALISTIC_PROMPT}"
        logger.info(f"🎨 Prompt: {full_prompt[:100]}...")
        
        image_bytes = await generate_with_cloudflare(
            prompt=full_prompt,
            width=1024,
            height=1024 if shot_type == "portrait" else 768,
            negative_prompt="blurry, low quality, distorted face, bad anatomy"
        )
        if not image_bytes:
            raise Exception("Cloudflare error")
        
        await edit_message(status_msg, "🔄 Заменяю лицо...") if isinstance(status_msg, types.CallbackQuery) else None
        
        result_bytes = await facefusion_client.swap_face(
            source_face_bytes=source_face,
            target_image_bytes=image_bytes
        )
        if not result_bytes:
            raise Exception("FaceFusion error")
        
        caption = truncate_caption(f"✅ Готово!\n🎨 Промпт: {prompt}\n✨ Стиль: {style}")
        if isinstance(status_msg, types.Message):
            await status_msg.delete()
        await send_photo(event, BufferedInputFile(result_bytes, filename="result.jpg"), caption=caption)
        
    except Exception as e:
        logger.exception("Generation error")
        error_text = truncate_caption(f"❌ Ошибка: {str(e)[:150]}")
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# 🔥 Простая генерация
# ------------------------------------------------------------
async def proceed_simple_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    prompt = event.text.strip() if isinstance(event, types.Message) else ""
    if not prompt:
        await send_message(event, "❌ Пустой промпт."); await state.clear(); return
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg); await state.clear(); return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Лимит исчерпан."); await state.clear(); return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую... ~30-60 сек")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(prompt)
        full_prompt = f"{translated}, {DEFAULT_REALISTIC_PROMPT}"
        
        image_bytes = await generate_with_cloudflare(
            prompt=full_prompt, width=1024, height=1024,
            negative_prompt="blurry, low quality"
        )
        if not image_bytes:
            raise Exception("Cloudflare error")
        
        caption = truncate_caption(f"✅ Готово!\n🎨 Промпт: {prompt}")
        if isinstance(status_msg, types.Message):
            await status_msg.delete()
        await send_photo(event, BufferedInputFile(image_bytes, filename="result.jpg"), caption=caption)
        
    except Exception as e:
        logger.exception("Simple generation error")
        error_text = truncate_caption(f"❌ Ошибка: {str(e)[:150]}")
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# 🔥 ИИ фотосессия
# ------------------------------------------------------------
async def proceed_photoshoot(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    source_image = data.get("source_image")
    gender = data.get("gender")
    shot_type = data.get("shot_type")
    prompt = event.text.strip() if isinstance(event, types.Message) else ""
    
    if not source_image or not prompt:
        await send_message(event, "❌ Ошибка данных."); await state.clear(); return
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg); await state.clear(); return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Лимит исчерпан."); await state.clear(); return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "🎭 Создаю фотосессию... ~30-60 сек")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(prompt)
        gender_text = "man" if gender == "male" else "woman"
        shot_text = "portrait, close-up" if shot_type == "portrait" else "full body shot"
        
        enhanced_prompt = f"{translated}, {gender_text}, {shot_text}, {DEFAULT_REALISTIC_PROMPT}, professional photo shoot"
        neg_prompt = "deformed, distorted, bad anatomy, blurry, ugly, watermark, low quality"
        
        logger.info(f"🎨 Photoshoot: '{prompt}' | gender={gender}, shot={shot_type}")
        
        result_bytes = await generate_inpainting_photoshoot(
            prompt=enhanced_prompt, source_image_bytes=source_image,
            width=512, height=512, strength=0.95, guidance=10.0, steps=20, negative_prompt=neg_prompt
        )
        if not result_bytes:
            raise Exception("Cloudflare error")
        
        caption = truncate_caption(f"✅ Готово!\n🎨 Промпт: {prompt}")
        if isinstance(status_msg, types.Message):
            await status_msg.delete()
        await send_photo(event, BufferedInputFile(result_bytes, filename="photoshoot.jpg"), caption=caption)
        
    except Exception as e:
        logger.exception("Photoshoot error")
        error_text = truncate_caption(f"❌ Ошибка: {str(e)[:150]}")
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# 🔥 Замена лица на своём фото
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_target_swap, F.photo | F.document)
async def receive_target_for_swap(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document and message.document.mime_type.startswith("image/"):
            photo = message.document
        if not photo:
            await message.answer("❌ Это не изображение."); return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        target_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        data = await state.get_data()
        source_face = data.get("source_face")
        if not source_face:
            await message.answer("❌ Не найдено исходное лицо."); await state.clear(); return
        
        user_id = message.from_user.id
        if not usage.increment(user_id):
            await message.answer("❌ Лимит исчерпан."); await state.clear(); return
        
        await state.set_state(UserStates.generating)
        status_msg = await message.answer("🔄 Заменяю лицо... ~60-90 сек")
        
        try:
            result_bytes = await facefusion_client.swap_face(
                source_face_bytes=source_face, target_image_bytes=target_image
            )
            if not result_bytes:
                raise Exception("FaceFusion error")
            caption = truncate_caption("✅ Готово! Лицо заменено. 🎭")
            await status_msg.delete()
            await message.answer_photo(photo=BufferedInputFile(result_bytes, filename="swapped.jpg"), caption=caption)
        except Exception as e:
            logger.exception("Face swap error")
            error_text = truncate_caption(f"❌ Ошибка: {str(e)[:150]}")
            await status_msg.edit_text(error_text)
        finally:
            await state.clear()
            await message.answer("Что дальше?", reply_markup=get_main_menu())
    except Exception as e:
        logger.exception("Error in receive_target_for_swap")
        await message.answer(f"❌ Ошибка: {str(e)}"); await state.clear()

# ------------------------------------------------------------
# 🔍 ДЕБАГ: Ловим необработанные callback
# ------------------------------------------------------------
@dp.callback_query()
async def debug_unhandled_callback(callback: types.CallbackQuery, state: FSMContext):
    """Ловит все callback, которые не обработались другими хендлерами"""
    current_state = await state.get_state()
    logger.warning(
        f"⚠️ Unhandled callback: '{callback.data}' "
        f"from user {callback.from_user.id} "
        f"in state {current_state}"
    )
    await callback.answer("⚠️ Эта функция ещё в разработке или произошла ошибка", show_alert=False)

# ------------------------------------------------------------
# Запуск
# ------------------------------------------------------------
async def on_startup(dispatcher: Dispatcher):
    try:
        await bot.set_webhook(
            config.WEBHOOK_URL,
            allowed_updates=["message", "callback_query", "chat_member"]
        )
        logger.info(f"✅ Webhook set to {config.WEBHOOK_URL}")
        try:
            await bot.send_message(config.ADMIN_ID, f"🚀 {config.BOT_NAME} запущен! ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        except:
            pass
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")

async def on_shutdown(dispatcher: Dispatcher):
    # 🔥 НЕ удаляем вебхук — Telegram сам управляет им
    # await bot.delete_webhook()
    logger.info("🛑 Bot stopped")
    if hasattr(bot, 'session') and bot.session:
        await bot.session.close()

def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    try:
        web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
