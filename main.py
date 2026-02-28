#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Main Bot File (FINAL VERSION)
- Генерация с заменой лица (портрет / полный рост)
- Простая генерация
- Замена лица на своём фото (без генерации)
- ✨ ИИ фотосессия (inpainting) – создание нового изображения на основе загруженного фото
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
# 🔑 ОБНОВЛЁННЫЙ ИМПОРТ: новые функции из cloudflare.py
from services.cloudflare import (
    generate_with_cloudflare,
    generate_inpainting_photoshoot,  # ← новая функция для фотосессии
    swap_face_after_flux,
    truncate_caption  # ← для обрезки caption до 1024 символов
)
from services.face_fusion_api import FaceFusionClient
from services.usage import UsageTracker

# ------------------------------------------------------------
# Константы
# ------------------------------------------------------------
SWAP_OWN_BUTTON = "🖼️ Замена лица на своём изображении"
PHOTOSHOOT_BUTTON = "✨ ИИ фотосессия"

# 🔑 ЛИМИТЫ TELEGRAM
MAX_PROMPT_LENGTH = 1024  # Максимальная длина промпта
MAX_CAPTION_LENGTH = 1024  # Лимит Telegram caption

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
# Универсальные функции отправки
# ------------------------------------------------------------
async def send_message(event: types.Message | types.CallbackQuery, text: str, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        return await event.message.answer(text, reply_markup=reply_markup)
    return await event.answer(text, reply_markup=reply_markup)

async def send_photo(event: types.Message | types.CallbackQuery, photo, caption: str = None, reply_markup=None):
    # 🔑 Обрезаем caption до лимита Telegram (1024 символа)
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
# 🔑 ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: проверка длины промпта
# ------------------------------------------------------------
def validate_prompt_length(prompt: str, max_length: int = MAX_PROMPT_LENGTH) -> tuple[bool, str]:
    """
    🔑 Проверяет длину промпта
    Возвращает: (is_valid, error_message_or_empty_string)
    """
    if not prompt or len(prompt.strip()) == 0:
        return False, "❌ Промпт не может быть пустым."
    
    if len(prompt) > max_length:
        return False, f"❌ Промпт слишком длинный (максимум {max_length} символов).\n\n💡 Совет: опишите главную идею короче."
    
    return True, ""

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
        "📝 **Важно**: длина промпта не должна превышать 1024 символа.\n\n"
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
        "📝 Максимальная длина промпта: 1024 символа.\n"
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
        "На основе этого фото я сгенерирую новые изображения в разных сценах.\n"
        "📝 Максимальная длина промпта: 1024 символа."
    )

# ------------------------------------------------------------
# Обработчики получения фото лица (для режима "С заменой лица")
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face, F.photo | F.document)
async def receive_face_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document:
            if message.document.mime_type.startswith("image/"):
                photo = message.document
            else:
                await message.answer("❌ Это не изображение. Отправьте, пожалуйста, фото.")
                return
        
        if not photo:
            await message.answer("❌ Не удалось получить изображение. Попробуйте ещё раз.")
            return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        source_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        data = await state.get_data()
        mode = data.get("mode")
        
        if mode == "generate":
            await state.update_data(face_image=source_image)
            await state.set_state(UserStates.waiting_for_gender)
            await message.answer("Выберите пол для генерации:", reply_markup=get_gender_keyboard())
        
        elif mode == "swap_own":
            await state.update_data(source_face=source_image)
            await state.set_state(UserStates.waiting_for_target_swap)
            await message.answer(
                "Теперь отправь фото, НА которое нужно заменить лицо.\n"
                "Это может быть любое изображение с человеком."
            )
            
    except Exception as e:
        logger.exception("Error receiving face photo")
        await message.answer(f"❌ Ошибка при обработке фото: {str(e)}")
        await state.clear()

# ------------------------------------------------------------
# Обработчик получения фото для фотосессии
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_face_photoshoot, F.photo | F.document)
async def receive_photoshoot_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1] if message.photo else None
        if not photo and message.document:
            if message.document.mime_type.startswith("image/"):
                photo = message.document
        
        if not photo:
            await message.answer("❌ Это не изображение. Отправьте фото.")
            return
        
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        source_image = file_bytes.read() if hasattr(file_bytes, 'read') else file_bytes
        
        await state.update_data(source_image=source_image)
        await state.set_state(UserStates.waiting_for_prompt_photoshoot)
        await message.answer(
            "🎨 Теперь напиши, в какой сцене или обстановке должен быть этот человек.\n"
            "📝 Максимальная длина: 1024 символа.\n"
            "Пример: на пляже на закате, в полный рост, профессиональное фото"
        )
        
    except Exception as e:
        logger.exception("Error receiving photoshoot photo")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

# ------------------------------------------------------------
# Обработчик выбора пола (с state-фильтром!)
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_gender, lambda c: c.data.startswith("gender_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.replace("gender_", "")
    await state.update_data(gender=gender)
    await state.set_state(UserStates.waiting_for_prompt)
    
    logger.info(f"👤 Gender selected: {gender} by user {callback.from_user.id}")
    
    await callback.message.edit_text(
        "✅ Пол учтён. Теперь напиши **текстовое описание** того, что должно быть на финальном изображении.\n"
        "📝 Максимальная длина: 1024 символа.\n"
        "Например: в костюме на фоне космоса"
    )

# ------------------------------------------------------------
# Обработчик выбора стиля
# ------------------------------------------------------------
@dp.callback_query(UserStates.waiting_for_prompt, lambda c: c.data.startswith("style_"))
async def process_style(callback: types.CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_", "")
    await state.update_data(chosen_style=style)
    await callback.message.edit_text(
        "✅ Стиль выбран. Теперь напиши описание для генерации.\n"
        "📝 Максимальная длина: 1024 символа."
    )

# ------------------------------------------------------------
# Обработчик промпта для режима "С заменой лица"
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt, F.text)
async def receive_prompt(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    # 🔑 ПРОВЕРКА ДЛИНЫ ПРОМПТА
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg)
        return
    
    await proceed_to_generation(message, state)

# ------------------------------------------------------------
# Обработчик промпта для "Просто генерация"
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_simple, F.text)
async def receive_prompt_simple(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    # 🔑 ПРОВЕРКА ДЛИНЫ ПРОМПТА
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg)
        return
    
    await proceed_simple_generation(message, state)

# ------------------------------------------------------------
# Обработчик промпта для фотосессии
# ------------------------------------------------------------
@dp.message(UserStates.waiting_for_prompt_photoshoot, F.text)
async def receive_prompt_photoshoot(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    # 🔑 ПРОВЕРКА ДЛИНЫ ПРОМПТА
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await message.answer(error_msg)
        return
    
    await proceed_photoshoot(message, state)

# ------------------------------------------------------------
# 🔥 ОСНОВНАЯ ФУНКЦИЯ: Генерация с заменой лица
# ------------------------------------------------------------
async def proceed_to_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    source_face = data.get("face_image")
    gender = data.get("gender")
    style = data.get("chosen_style")
    prompt = data.get("prompt") if isinstance(event, types.CallbackQuery) else event.text.strip()
    
    if not source_face or not prompt:
        await send_message(event, "❌ Ошибка: не хватает данных. Начни заново.")
        await state.clear()
        return
    
    # 🔑 ПРОВЕРКА ДЛИНЫ ПРОМПТА
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg)
        await state.clear()
        return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую изображение через Cloudflare (FLUX)...")
    
    try:
        # Перевод промпта на английский
        translator = GoogleTranslator(source='auto', target='en')
        translated_prompt = translator.translate(prompt)
        
        # Формируем полный промпт
        gender_text = "профессиональное фото мужчины" if gender == "male" else "профессиональное фото девушки"
        
        # 🔑 style УЖЕ включён в промпт, не передаём отдельным параметром!
        full_prompt = f"{translated_prompt}, {gender_text}, {style}, professional photography, sharp focus, 8k"
        
        # 🔑 ИСПРАВЛЕНО: УБРАН параметр style= из вызова!
        image_bytes = await generate_with_cloudflare(
            prompt=full_prompt,
            width=1024,
            height=1024,
            negative_prompt="blurry, low quality, distorted face, extra limbs, bad anatomy"
        )
        
        if not image_bytes:
            raise Exception("Cloudflare не вернул изображение")
        
        # Замена лица через FaceFusion
        await edit_message(status_msg, "🔄 Выполняю замену лица...") if isinstance(status_msg, types.CallbackQuery) else None
        
        result_bytes = await facefusion_client.swap_face(
            source_face_bytes=source_face,
            target_image_bytes=image_bytes
        )
        
        if not result_bytes:
            raise Exception("FaceFusion не вернул результат")
        
        # 🔑 Обрезаем caption до 1024 символов
        caption = truncate_caption(f"✅ Готово (с заменой лица)!\n🎨 Промпт: {prompt}\n✨ Стиль: {style}")
        
        if isinstance(status_msg, types.Message):
            await status_msg.delete()
        
        await send_photo(event, BufferedInputFile(result_bytes, filename="result.jpg"), caption=caption)
        
    except Exception as e:
        logger.exception("Generation error")
        error_text = truncate_caption(f"❌ Ошибка генерации: {str(e)[:150]}")
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# 🔥 ПРОСТАЯ ГЕНЕРАЦИЯ (без лица)
# ------------------------------------------------------------
async def proceed_simple_generation(event: types.Message | types.CallbackQuery, state: FSMContext):
    prompt = (await state.get_data()).get("prompt") if isinstance(event, types.CallbackQuery) else event.text.strip()
    
    if not prompt:
        await send_message(event, "❌ Ошибка: пустой промпт.")
        await state.clear()
        return
    
    # 🔑 ПРОВЕРКА ДЛИНЫ
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg)
        await state.clear()
        return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "⏳ Генерирую изображение...")
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(prompt)
        
        image_bytes = await generate_with_cloudflare(
            prompt=translated,
            width=1024,
            height=1024,
            negative_prompt="blurry, low quality, distorted"
        )
        
        if not image_bytes:
            raise Exception("Cloudflare не вернул изображение")
        
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
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# 🔥 ИИ ФОТОСЕССИЯ (inpainting с маской лица)
# ------------------------------------------------------------
async def proceed_photoshoot(event: types.Message | types.CallbackQuery, state: FSMContext):
    """
    ✨ ИИ фотосессия: фото пользователя + промпт → inpainting с сохранением лица
    """
    data = await state.get_data()
    source_image = data.get("source_image")
    prompt = data.get("photoshoot_prompt") if isinstance(event, types.CallbackQuery) else event.text.strip()
    
    if not source_image or not prompt:
        await send_message(event, "❌ Ошибка: не хватает данных. Начни заново.")
        await state.clear()
        return
    
    # 🔑 ПРОВЕРКА ДЛИНЫ ПРОМПТА
    is_valid, error_msg = validate_prompt_length(prompt)
    if not is_valid:
        await send_message(event, error_msg)
        await state.clear()
        return
    
    user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
    if not usage.increment(user_id):
        await send_message(event, "❌ Дневной лимит исчерпан.")
        await state.clear()
        return
    
    await state.set_state(UserStates.generating)
    status_msg = await send_message(event, "🎭 Определяю лицо...")
    
    try:
        # 🔑 Перевод промпта на английский
        translator = GoogleTranslator(source='auto', target='en')
        translated_prompt = translator.translate(prompt)
        
        # 🔑 Усиленный промпт для качества фона
        quality_suffix = (
            ", professional photography, cinematic lighting, sharp focus, "
            "8k uhd, dslr, soft lighting, high quality, film grain, "
            "detailed background, realistic, depth of field, bokeh"
        )
        enhanced_prompt = f"{translated_prompt}{quality_suffix}"
        
        # 🔑 Negative prompt для чистого результата
        neg_prompt = (
            "deformed, distorted, disfigured, bad anatomy, extra limb, "
            "blurry, ugly, mutated, watermark, text, signature, "
            "low quality, jpeg artifacts, cartoon, anime, 3d render"
        )
        
        # 🔥 Запускаем inpainting-фотосессию (НОВАЯ ФУНКЦИЯ!)
        logger.info(f"🎨 Photoshoot: '{prompt}' | face detection → inpainting")
        
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
        
        # 🔑 Обрезаем caption до 1024 символов
        caption = truncate_caption(f"✅ Готово!\n🎨 Промпт: {prompt}")
        
        if isinstance(status_msg, types.Message):
            await status_msg.delete()
        
        await send_photo(event, BufferedInputFile(result_bytes, filename="photoshoot.jpg"), caption=caption)
        
    except Exception as e:
        logger.exception("❌ Photoshoot error")
        error_text = truncate_caption(f"❌ Ошибка генерации: {str(e)[:150]}")
        if isinstance(status_msg, types.Message):
            await status_msg.edit_text(error_text)
        else:
            await send_message(event, error_text)
    finally:
        await state.clear()
        await send_message(event, "Что делаем дальше?", reply_markup=get_main_menu())

# ------------------------------------------------------------
# 🔥 ЗАМЕНА ЛИЦА НА СВОЁМ ФОТО (без генерации)
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
            await message.answer("❌ Ошибка: не найдено исходное лицо.")
            await state.clear()
            return
        
        user_id = message.from_user.id
        if not usage.increment(user_id):
            await message.answer("❌ Дневной лимит исчерпан.")
            await state.clear()
            return
        
        await state.set_state(UserStates.generating)
        status_msg = await message.answer("🔄 Выполняю замену лица...")
        
        try:
            result_bytes = await facefusion_client.swap_face(
                source_face_bytes=source_face,
                target_image_bytes=target_image
            )
            
            if not result_bytes:
                raise Exception("FaceFusion не вернул результат")
            
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
            await message.answer("Что делаем дальше?", reply_markup=get_main_menu())
            
    except Exception as e:
        logger.exception("Error in receive_target_for_swap")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

# ------------------------------------------------------------
# 🔍 ДЕБАГ: Ловим необработанные callback (для отладки)
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
    await callback.answer("⚠️ Этот запрос ещё в разработке или произошла ошибка", show_alert=True)

# ------------------------------------------------------------
# Запуск вебхука
# ------------------------------------------------------------
async def on_startup(dispatcher: Dispatcher):
    await bot.set_webhook(config.WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {config.WEBHOOK_URL}")
    try:
        await bot.send_message(config.ADMIN_ID, f"🚀 {config.BOT_NAME} запущен! ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    except:
        pass

async def on_shutdown(dispatcher: Dispatcher):
    # await bot.delete_webhook()
    logger.info("🛑 Bot stopped")

# ------------------------------------------------------------
# Основной запуск
# ------------------------------------------------------------
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
