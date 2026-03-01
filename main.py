#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot File (FINAL FIXED)
- Генерация с заменой лица + выбор стиля и типа кадра
- Простая генерация
- Замена лица на своём фото
- ✨ ИИ фотосессия с выбором пола и типа кадра
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
    swap_face_after_flux,
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

# 🔥 ДЕФОЛТНЫЙ ПРОМПТ ДЛЯ РЕАЛИЗМА
DEFAULT_REALISTIC_PROMPT = (
    "professional photography, photorealistic, sharp focus, 8k uhd, "
    "dslr, soft lighting, high quality, film grain, natural skin texture, "
    "realistic details, depth of field, bokeh, studio lighting"
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
async def send_message(event: types.Message | types.CallbackQuery, text: str, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        return await event.message.answer(text, reply_markup=reply_markup)
    return await event.answer(text, reply_markup=reply_markup)

async def send_photo(event: types.Message | types.CallbackQuery, photo, caption: str = None, reply_markup=None):
    if caption:
        caption = truncate_caption(caption, max_length=MAX_CAPTION_LENGTH)
    
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
# Проверка длины промпта
# ------------------------------------------------------------
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
        "Я могу:\n"
        "🔄 **С заменой лица**: загружаешь фото → генерирую картинку → вставляю твоё лицо\n"
        "✨ **Просто генерация**: создаю изображение только по тексту\n"
        f"{SWAP_OWN_BUTTON}: меняю лицо на твоём фото\n"
        f"{PHOTOSHOOT_BUTTON}: создаю фотосессию с твоим лицом в новой обстановке\n\n"
        "📝 Промпт максимум 1024 символа.\n\n"
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
        await message.answer("❌ Дневной лимит исчерпан.")
        return
    await state.set_state(UserStates.waiting_for_face)
    await state.update_data(mode="generate")
    await message.answer(
        "Отправь фото с лицом (анфас, хорошее освещение).\n"
        "📝 Чем лучше фото, тем качественнее результат!"
    )

@dp.message(lambda msg: msg.text == "✨ Просто генерация")
async def simple_generation_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Дневной лимит исчерпан.")
        return
    await state.set_state(UserStates.waiting_for_prompt_simple)
    await message.answer(
        "Напиши описание что сгенерировать.\n"
        "📝 Максимум 1024 символа.\n"
        "Пример: красивый закат над горами, цифровое искусство"
    )

@dp.message(lambda msg: msg.text == SWAP_OWN_BUTTON)
async def swap_own_image_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Дневной лимит исчерпан.")
        return
    await state.set_state(UserStates.waiting_for_face)
    await state.update_data(mode="swap_own")
    await message.answer(
        "Отправь фото лица которое нужно вставить.\n"
        "После этого отправь фото НА которое заменить."
    )

@dp.message(lambda msg: msg.text == PHOTOSHOOT_BUTTON)
async def photoshoot_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not usage.check_limit(user_id):
        await message.answer("❌ Дневной лимит исчерпан.")
        return
    await state.set_state(UserStates.waiting_for_face_photoshoot)
    await state.update_data(mode="photoshoot")
    await message.answer(
        "📸 Отправь фото человека для фотосессии.\n"
        "📝 Лицо должно быть чётко видно, анфас."
    )

# ------------------------------------------------------------
# Получение фото лица
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face, F.photo | F.document)
async def receive_face_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document:
            if message.document.mime_type.startswith("image/"):
                photo = message.document
        
        if not photo:
            await message.answer("❌ Это не изображение.")
            return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        source_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        data = await state.get_data()
        mode = data.get("mode")
        
        if mode == "generate":
            await state.update_data(face_image=source_image)
            await state.set_state(UserStates.waiting_for_gender)
            await message.answer("Выберите пол:", reply_markup=get_gender_keyboard())
        
        elif mode == "swap_own":
            await state.update_data(source_face=source_image)
            await state.set_state(UserStates.waiting_for_target_swap)
            await message.answer(
                "Теперь отправь фото НА которое заменить лицо."
            )
            
    except Exception as e:
        logger.exception("Error receiving face photo")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

# ------------------------------------------------------------
# Получение фото для фотосессии
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face_photoshoot, F.photo | F.document)
async def receive_photoshoot_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document:
            if message.document.mime_type.startswith("image/"):
                photo = message.document
        
        if not photo:
            await message.answer("❌ Это не изображение.")
            return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        source_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        await state.update_data(source_image=source_image)
        # 🔥 ДОБАВЛЕНО: Выбор пола для фотосессии
        await state.set_state(UserStates.waiting_for_gender_photoshoot)
        await message.answer(
            "🎨 Выберите пол для фотосессии:",
            reply_markup=get_gender_keyboard()
        )
        
    except Exception as e:
        logger.exception("Error receiving photoshoot photo")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

# ------------------------------------------------------------
# Выбор пола (режим генерации)
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_gender, lambda c: c.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    # 🔥 ДОБАВЛЕНО: Переход к выбору стиля
    await state.set_state(UserStates.waiting_for_style)
    
    logger.info(f"👤 Gender selected: {gender}")
    
    await callback.message.edit_text(
        "✅ Пол учтён. Теперь выберите стиль:",
        reply_markup=get_style_keyboard()
    )

# ------------------------------------------------------------
# Выбор пола (фотосессия)
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_gender_photoshoot, lambda c: c.data.startswith("gender_"))
async def process_gender_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    # 🔥 ДОБАВЛЕНО: Переход к выбору типа кадра для фотосессии
    await state.set_state(UserStates.waiting_for_shot_type_photoshoot)
    
    logger.info(f"👤 Photoshoot gender: {gender}")
    
    await callback.message.edit_text(
        "✅ Пол учтён. Выберите тип кадра:",
        reply_markup=get_shot_type_keyboard()
    )

# ------------------------------------------------------------
# Выбор стиля
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_style, lambda c: c.data.startswith("style_"))
async def process_style(callback: types.CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")
    await state.update_data(chosen_style=style)
    # 🔥 Переход к выбору типа кадра
    await state.set_state(UserStates.waiting_for_shot_type)
    
    logger.info(f"🎨 Style selected: {style}")
    
    await callback.message.edit_text(
        "✅ Стиль выбран. Выберите тип кадра:",
        reply_markup=get_shot_type_keyboard()
    )

# ------------------------------------------------------------
# Выбор типа кадра (режим генерации)
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_shot_type, lambda c: c.data.startswith("shot_"))
async def process_shot_type(callback: types.CallbackQuery, state: FSMContext):
    shot_type = callback.data.replace("shot_", "")
    await state.update_data(shot_type=shot_type)
    await state.set_state(UserStates.waiting_for_prompt)
    
    shot_text = "портрет (лицо и плечи)" if shot_type == "portrait" else "в полный рост"
    
    logger.info(f"📐 Shot type: {shot_type}")
    
    await callback.message.edit_text(
        f"✅ Тип кадра: {shot_text}.\n\n"
        f"Теперь напишите описание сцены:\n"
        f"📝 Максимум 1024 символа.\n\n"
        f"💡 Пример: в костюме на фоне космоса, неон, киберпанк"
    )

# ------------------------------------------------------------
# Выбор типа кадра (фотосессия)
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_shot_type_photoshoot, lambda c: c.data.startswith("shot_"))
async def process_shot_type_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    shot_type = callback.data.replace("shot_", "")
    await state.update_data(shot_type=shot_type)
    await state.set_state(UserStates.waiting_for_prompt_photoshoot)
    
    shot_text = "портрет" if shot_type == "portrait" else "в полный рост"
    
    logger.info(f"📐 Photoshoot shot type: {shot_type}")
    
    await callback.message.edit_text(
        f"✅ Тип кадра: {shot_text}.\n\n"
        f"Теперь опишите сцену где должен быть человек:\n"
        f"📝 Максимум 1024 символа.\n\n"
        f"💡 Пример: на пляже на закате, профессиональное фото\n"
        f"🔥 По умолчанию добавлю реализм (профессиональное фото, 8k, детали)"
    )

# ------------------------------------------------------------
# Промпт для режима генерации
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt, F.text)
async def receive_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg)
        return
    
    await proceed_to_generation(message, state)

# ------------------------------------------------------------
# Промпт для простой генерации
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_simple, F.text)
async def receive_prompt_simple(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg)
        return
    
    await proceed_simple_generation(message, state)

# ------------------------------------------------------------
# Промпт для фотосессии
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_photoshoot, F.text)
async def receive_prompt_photoshoot(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg)
        return
    
    await proceed_photoshoot(message, state)

# ------------------------------------------------------------
# 🔥 ГЕНЕРАЦИЯ С ЗАМЕНОЙ ЛИЦА
# ------------------------------------------------------------
async def proceed_to_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    source_face = data.get("face_image")
    gender = data.get("gender")
    style = data.get("chosen_style")
    shot_type = data.get("shot_type")
    prompt = event.text.strip() if isinstance(event, types.Message) else data.get("prompt")
    
    if not source_face or not prompt:
        await send_message(event, "❌ Ошибка данных. Начните заново.")
        await state.clear()
        return
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg)
        await state.clear()
        return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Лимит исчерпан.")
        await state.clear()
        return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую... ~60-90 сек")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated_prompt = translator.translate(prompt)
        
        gender_text = "man" if gender == "male" else "woman"
        shot_text = "portrait, close-up" if shot_type == "portrait" else "full body shot"
        
        # 🔥 Добавляем дефолтный реализм
        full_prompt = f"{translated_prompt}, {gender_text}, {shot_text}, {style}, {DEFAULT_REALISTIC_PROMPT}"
        
        logger.info(f"🎨 Full prompt: {full_prompt[:100]}...")
        
        image_bytes = await generate_with_cloudflare(
            prompt=full_prompt,
            width=1024,
            height=1024 if shot_type == "portrait" else 768,
            negative_prompt="blurry, low quality, distorted face, bad anatomy"
        )
        
        if not image_bytes:
            raise Exception("Cloudflare не вернул изображение")
        
        await edit_message(status_msg, "🔄 Заменяю лицо...") if isinstance(status_msg, types.CallbackQuery) else None
        
        result_bytes = await facefusion_client.swap_face(
            source_face_bytes=source_face,
            target_image_bytes=image_bytes
        )
        
        if not result_bytes:
            raise Exception("FaceFusion не вернул результат")
        
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
# 🔥 ПРОСТАЯ ГЕНЕРАЦИЯ
# ------------------------------------------------------------
async def proceed_simple_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    prompt = event.text.strip() if isinstance(event, types.Message) else ""
    
    if not prompt:
        await send_message(event, "❌ Пустой промпт.")
        await state.clear()
        return
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg)
        await state.clear()
        return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Лимит исчерпан.")
        await state.clear()
        return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую... ~30-60 сек")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(prompt)
        
        # 🔥 Добавляем реализм
        full_prompt = f"{translated}, {DEFAULT_REALISTIC_PROMPT}"
        
        image_bytes = await generate_with_cloudflare(
            prompt=full_prompt,
            width=1024,
            height=1024,
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
# 🔥 ИИ ФОТОСЕССИЯ
# ------------------------------------------------------------
async def proceed_photoshoot(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    source_image = data.get("source_image")
    gender = data.get("gender")
    shot_type = data.get("shot_type")
    prompt = event.text.strip() if isinstance(event, types.Message) else ""
    
    if not source_image or not prompt:
        await send_message(event, "❌ Ошибка данных.")
        await state.clear()
        return
    
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg)
        await state.clear()
        return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Лимит исчерпан.")
        await state.clear()
        return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "🎭 Создаю фотосессию... ~30-60 сек")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated_prompt = translator.translate(prompt)
        
        # 🔥 Добавляем реализм + параметры кадра
        gender_text = "man" if gender == "male" else "woman"
        shot_text = "portrait, close-up of face" if shot_type == "portrait" else "full body shot"
        
        enhanced_prompt = (
            f"{translated_prompt}, {gender_text}, {shot_text}, "
            f"{DEFAULT_REALISTIC_PROMPT}, professional photo shoot, "
            "cinematic lighting, detailed background, realistic"
        )
        
        neg_prompt = (
            "deformed, distorted, bad anatomy, extra limb, blurry, "
            "ugly, mutated, watermark, text, low quality, cartoon"
        )
        
        logger.info(f"🎨 Photoshoot: '{prompt}' | gender={gender}, shot={shot_type}")
        
        result_bytes = await generate_inpainting_photoshoot(
            prompt=enhanced_prompt,
            source_image_bytes=source_image,
            width=512,
            height=512,
            strength=0.95,
            guidance=10.0,
            steps=20,
            negative_prompt=neg_prompt
        )
        
        if not result_bytes:
            raise Exception("Cloudflare не вернул изображение")
        
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
# 🔥 ЗАМЕНА ЛИЦА НА СВОЁМ ФОТО
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_target_swap, F.photo | F.document)
async def receive_target_for_swap(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document:
            if message.document.mime_type.startswith("image/"):
                photo = message.document
        
        if not photo:
            await message.answer("❌ Это не изображение.")
            return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        target_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        data = await state.get_data()
        source_face = data.get("source_face")
        
        if not source_face:
            await message.answer("❌ Не найдено исходное лицо.")
            await state.clear()
            return
        
        user_id = message.from_user.id
        if not usage.increment(user_id):
            await message.answer("❌ Лимит исчерпан.")
            await state.clear()
            return
        
        await state.set_state(UserStates.generating)
        status_msg = await message.answer("🔄 Заменяю лицо... ~60-90 сек")
        
        try:
            result_bytes = await facefusion_client.swap_face(
                source_face_bytes=source_face,
                target_image_bytes=target_image
            )
            
            if not result_bytes:
                raise Exception("FaceFusion error")
            
            caption = truncate_caption("✅ Готово! Лицо заменено. 🎭")
            await status_msg.delete()
            await message.answer_photo(
                photo=BufferedInputFile(result_bytes, filename="swapped.jpg"),
                caption=caption
            )
            
        except Exception as e:
            logger.exception("Face swap error")
            error_text = truncate_caption(f"❌ Ошибка: {str(e)[:150]}")
            await status_msg.edit_text(error_text)
        finally:
            await state.clear()
            await message.answer("Что дальше?", reply_markup=get_main_menu())
            
    except Exception as e:
        logger.exception("Error in receive_target_for_swap")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

# ------------------------------------------------------------
# Запуск
# ------------------------------------------------------------
async def on_startup(dispatcher: Dispatcher):
    await bot.set_webhook(config.WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {config.WEBHOOK_URL}")
    try:
        await bot.send_message(config.ADMIN_ID, f"🚀 {config.BOT_NAME} запущен!")
    except:
        pass

async def on_shutdown(dispatcher: Dispatcher):
    await bot.delete_webhook()
    logger.info("🛑 Bot stopped")

def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    main()
