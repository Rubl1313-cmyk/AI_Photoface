# 🚀 Полностью рабочий бот с 3 категориями
# AI Photoshoot, AI Styles, AIMage
import asyncio
import logging
import os
import tempfile
import shutil
from pathlib import Path
from aiogram import Bot, types, F, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardBuilder
from fastapi import FastAPI
import uvicorn
import httpx
import base64
import io
import json

import config
from services.phoenix_cloudflare import generate_with_flux_klein, generate_with_flux_schnell
from services.usage import UsageTracker
from modern_states import UserStates
from modern_keyboards import (
    get_main_menu, 
    get_photoshoot_styles_keyboard,
    get_ai_styles_keyboard,
    get_photoshoot_formats_keyboard,
    get_back_menu
)
from prompts import (
    PHOTOSHOOT_REALISM,
    AI_STYLES,
    PHOTOSHOOT_FORMATS,
    build_photoshoot_prompt,
    get_photoshoot_negative_prompt,
    build_ai_styles_prompt
)

# Константы
from config import DATA_DIR

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT)

# Вспомогательная функция для отправки фото
async def send_photo(message, photo, caption=None, reply_markup=None):
    """Отправка фото с автоматическим определением типа"""
    try:
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото: {e}")
        await message.answer("❌ Не удалось отправить фото")

# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    
    await message.answer("🎨 **AI PhotoStudio 2.0**", reply_markup=ReplyKeyboardRemove())
    
    await message.answer(
        "✨ *Профессиональные фотографии с ИИ*\n\n"
        "🎯 **3 категории:**\n"
        "📸 **AI Photoshoot** - реалистичные фото с твоим лицом\n"
        "🎨 **AI Styles** - популярные стили с референсом\n"
        "🎯 **AIMage** - генерация по промпту\n\n"
        f"💡 *Лимит: {usage.daily_limit} фото в день!*\n"
        "🚀 *FLUX.2-klein и FLUX.1-schnell технологии!*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# AI Photoshoot
@dp.callback_query(F.data == "ai_photoshoot")
async def handle_ai_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_photoshoot_face)
    await callback.message.edit_text(
        "📸 **AI Photoshoot - Фотореализм**\n\n"
        "🎯 Создаю профессиональные фотографии с твоим лицом\n"
        "💡 *Использую FLUX.2-klein для максимального качества!*\n\n"
        "👇 *Отправь своё фото* (хорошего качества, лицо видно четко)",
        parse_mode="Markdown"
    )

# AI Styles
@dp.callback_query(F.data == "ai_styles")
async def handle_ai_styles(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_ai_styles_face)
    await callback.message.edit_text(
        "🎨 **AI Styles - Популярные стили 2026**\n\n"
        "🎯 Создаю изображения с твоим лицом в разных стилях\n"
        "💡 *Использую FLUX.2-klein и формат 16:9!*\n\n"
        "👇 *Отправь своё фото* (хорошего качества, лицо видно четко)",
        parse_mode="Markdown"
    )

# AIMage
@dp.callback_query(F.data == "ai_image")
async def handle_ai_image(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_ai_image_prompt)
    await callback.message.edit_text(
        "🎨 **AIMage - Генерация по промпту**\n\n"
        "🎯 Создаю изображения по твоему описанию\n"
        "💡 *Использую FLUX.1-schnell для быстрой генерации!*\n\n"
        "👇 *Напиши промпт для генерации*",
        parse_mode="Markdown"
    )

# Обработчики фото и документов
@dp.message(F.photo | F.document)
async def handle_photo_upload(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    # AI Photoshoot - загрузка фото
    if current_state == UserStates.waiting_for_photoshoot_face:
        if message.photo:
            photo_file = await bot.get_file(message.photo[-1].file_id)
            photo_bytes = await bot.download_file(photo_file.file_path)
            await state.update_data(photoshoot_face=photo_bytes.read())
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            doc_file = await bot.get_file(message.document.file_id)
            doc_bytes = await bot.download_file(doc_file.file_path)
            await state.update_data(photoshoot_face=doc_bytes.read())
        else:
            await message.answer("❌ Пожалуйста, отправьте фото или изображение")
            return
        
        await state.set_state(UserStates.selecting_photoshoot_style)
        await message.answer(
            "📸 **Выбери стиль фотосессии**\n\n"
            "💡 *Только фотореалистичные стили для качественных фотографий*",
            reply_markup=get_photoshoot_styles_keyboard(),
            parse_mode="Markdown"
        )
    
    # AI Styles - загрузка фото
    elif current_state == UserStates.waiting_for_ai_styles_face:
        if message.photo:
            photo_file = await bot.get_file(message.photo[-1].file_id)
            photo_bytes = await bot.download_file(photo_file.file_path)
            await state.update_data(ai_styles_face=photo_bytes.read())
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            doc_file = await bot.get_file(message.document.file_id)
            doc_bytes = await bot.download_file(doc_file.file_path)
            await state.update_data(ai_styles_face=doc_bytes.read())
        else:
            await message.answer("❌ Пожалуйста, отправьте фото или изображение")
            return
        
        await state.set_state(UserStates.selecting_ai_styles_style)
        await message.answer(
            "🎨 **Выбери стиль**\n\n"
            "💡 *30 популярных стилей 2026 года!*",
            reply_markup=get_ai_styles_keyboard(),
            parse_mode="Markdown"
        )

# AI Photoshoot - выбор стиля
@dp.callback_query(F.data.startswith("photoshoot_style_"))
async def handle_photoshoot_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_")[2]
    
    if style_key not in PHOTOSHOOT_REALISM:
        await callback.answer("❌ Стиль не найден", show_alert=True)
        return
    
    style = PHOTOSHOOT_REALISM[style_key]
    await state.update_data(photoshoot_style=style_key)
    
    # Показываем выбор формата
    await state.set_state(UserStates.selecting_photoshoot_format)
    examples_text = "\n".join([f"• {ex}" for ex in style["examples"]])
    
    await callback.message.edit_text(
        f"📸 **{style['name']}**\n\n"
        f"📝 {style['description']}\n\n"
        f"💡 **Примеры локаций:**\n{examples_text}\n\n"
        f"📐 **Теперь выбери формат:**",
        reply_markup=get_photoshoot_formats_keyboard(),
        parse_mode="Markdown"
    )

# AI Photoshoot - выбор формата
@dp.callback_query(F.data.startswith("photoshoot_format_"))
async def handle_photoshoot_format(callback: types.CallbackQuery, state: FSMContext):
    format_key = callback.data.split("_")[2]
    
    if format_key not in PHOTOSHOOT_FORMATS:
        await callback.answer("❌ Формат не найден", show_alert=True)
        return
    
    format_info = PHOTOSHOOT_FORMATS[format_key]
    await state.update_data(photoshoot_format=format_key)
    
    # Запрашиваем пользовательский промпт
    await state.set_state(UserStates.waiting_for_photoshoot_prompt)
    
    await callback.message.edit_text(
        f"📐 **{format_info['name']}**\n\n"
        f"📝 {format_info['description']}\n\n"
        f"✍️ **Добавь детали для генерации:**\n"
        f"• Где находится? (на крыше, в кафе, на пляже)\n"
        f"• Во что одет? (в джинсах, в вечернем платье)\n"
        f"• Какое настроение? (счастливый, задумчивый)\n"
        f"• Освещение? (естественное, неоновое)\n\n"
        f"👇 *Напиши детали или отправь 'готово' для генерации*",
        parse_mode="Markdown"
    )

# AI Styles - выбор стиля
@dp.callback_query(F.data.startswith("ai_style_"))
async def handle_ai_styles_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_")[2]
    
    if style_key not in AI_STYLES:
        await callback.answer("❌ Стиль не найден", show_alert=True)
        return
    
    style = AI_STYLES[style_key]
    await state.update_data(ai_styles_style=style_key)
    
    # Запрашиваем пользовательский промпт
    await state.set_state(UserStates.waiting_for_ai_styles_prompt)
    
    await callback.message.edit_text(
        f"🎨 **{style['name']}**\n\n"
        f"📝 {style['description']}\n\n"
        f"✍️ **Добавь детали для генерации:**\n"
        f"• Что еще добавить? (дополнительные элементы)\n"
        f"• Какое настроение? (яркое, мрачное, мистическое)\n"
        f"• Особенности? (фон, детали, атмосфера)\n\n"
        f"👇 *Напиши детали или отправь 'готово' для генерации*",
        parse_mode="Markdown"
    )

# Обработчики текстовых сообщений
@dp.message()
async def handle_text_messages(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    user_text = message.text.strip()
    
    # AI Photoshoot - промпт
    if current_state == UserStates.waiting_for_photoshoot_prompt:
        if user_text.lower() in ['готово', 'дальше', 'continue', '']:
            await process_photoshoot_generation(message, state, "")
        else:
            await state.update_data(photoshoot_prompt=user_text)
            await message.answer(
                "✅ *Детали добавлены!*\n\n"
                "👇 *Отправь 'готово' для генерации или добавь еще деталей*",
                parse_mode="Markdown"
            )
    
    # AI Styles - промпт
    elif current_state == UserStates.waiting_for_ai_styles_prompt:
        if user_text.lower() in ['готово', 'дальше', 'continue', '']:
            await process_ai_styles_generation(message, state, "")
        else:
            await state.update_data(ai_styles_prompt=user_text)
            await message.answer(
                "✅ *Детали добавлены!*\n\n"
                "👇 *Отправь 'готово' для генерации или добавь еще деталей*",
                parse_mode="Markdown"
            )
    
    # AIMage - промпт
    elif current_state == UserStates.waiting_for_ai_image_prompt:
        await process_ai_image_generation(message, state, user_text)

# Функции генерации
async def process_photoshoot_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    """Обработка генерации AI Photoshoot с FLUX.2-klein"""
    await state.set_state(UserStates.generating_photoshoot)
    await message.answer("📸 *Создаю профессиональные фотографии...*", parse_mode="Markdown")
    
    try:
        data = await state.get_data()
        face_photo = data.get("photoshoot_face")
        style_key = data.get("photoshoot_style", "portrait")
        format_key = data.get("photoshoot_format", "vertical_4_3")
        user_prompt = custom_prompt or data.get("photoshoot_prompt", "")
        
        if not face_photo:
            await message.answer("❌ Фото не найдено. Начни заново")
            await state.set_state(UserStates.idle)
            return
        
        # Проверка лимита
        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(
                f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})"
            )
            await state.set_state(UserStates.idle)
            return
        
        # Получаем параметры формата
        format_info = PHOTOSHOOT_FORMATS[format_key]
        
        # Собираем финальный промпт
        final_prompt = build_photoshoot_prompt(style_key, "selfie", user_prompt)
        negative_prompt = get_photoshoot_negative_prompt(style_key)
        
        logger.info(f"📸 AI Photoshoot: {style_key} - {final_prompt[:100]}...")
        
        # Генерируем с FLUX.2-klein с референсом
        result_image = await generate_with_flux_klein(
            prompt=final_prompt,
            reference_image=face_photo,
            width=format_info["width"],
            height=format_info["height"],
            steps=28,
            guidance=7.5,
            negative_prompt=negative_prompt
        )
        
        if result_image:
            style = PHOTOSHOOT_REALISM[style_key]
            
            caption = (
                f"📸 **{style['name']} готов!**\n\n"
                f"📐 Формат: {format_info['name']}\n"
                f"📝 Детали: `{user_prompt if user_prompt else 'Базовый стиль'}`\n"
                f"✨ Создано с AI PhotoStudio 2.0 + FLUX.2-klein"
            )
            
            await send_photo(
                message,
                BufferedInputFile(result_image, filename="photoshoot.jpg"),
                caption=caption,
                reply_markup=get_main_menu()
            )
            
            usage.record_generation(user_id)
            logger.info(f"✅ AI Photoshoot completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")
    
    except Exception as e:
        logger.error(f"❌ AI Photoshoot error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    
    finally:
        await state.set_state(UserStates.idle)

async def process_ai_styles_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    """Обработка генерации AI Styles с FLUX.2-klein"""
    await state.set_state(UserStates.generating_ai_styles)
    await message.answer("🎨 *Создаю стилизованное изображение...*", parse_mode="Markdown")
    
    try:
        data = await state.get_data()
        face_photo = data.get("ai_styles_face")
        style_key = data.get("ai_styles_style", "cyberpunk")
        user_prompt = custom_prompt or data.get("ai_styles_prompt", "")
        
        if not face_photo:
            await message.answer("❌ Фото не найдено. Начни заново")
            await state.set_state(UserStates.idle)
            return
        
        # Проверка лимита
        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(
                f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})"
            )
            await state.set_state(UserStates.idle)
            return
        
        # Собираем финальный промпт
        final_prompt = build_ai_styles_prompt(style_key, user_prompt)
        
        logger.info(f"🎨 AI Styles: {style_key} - {final_prompt[:100]}...")
        
        # Генерируем с FLUX.2-klein с референсом, формат 16:9
        result_image = await generate_with_flux_klein(
            prompt=final_prompt,
            reference_image=face_photo,
            width=1024,
            height=576,  # 16:9 формат
            steps=28,
            guidance=7.5
        )
        
        if result_image:
            style = AI_STYLES[style_key]
            
            caption = (
                f"🎨 **{style['name']} готов!**\n\n"
                f"📝 Детали: `{user_prompt if user_prompt else 'Базовый стиль'}`\n"
                f"📐 Формат: 16:9\n"
                f"✨ Создано с AI PhotoStudio 2.0 + FLUX.2-klein"
            )
            
            await send_photo(
                message,
                BufferedInputFile(result_image, filename="ai_styles.jpg"),
                caption=caption,
                reply_markup=get_main_menu()
            )
            
            usage.record_generation(user_id)
            logger.info(f"✅ AI Styles completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")
    
    except Exception as e:
        logger.error(f"❌ AI Styles error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    
    finally:
        await state.set_state(UserStates.idle)

async def process_ai_image_generation(message: types.Message, state: FSMContext, prompt: str):
    """Обработка генерации AIMage с FLUX.1-schnell"""
    await state.set_state(UserStates.generating_ai_image)
    await message.answer("🎨 *Генерирую изображение...*", parse_mode="Markdown")
    
    try:
        # Проверка лимита
        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(
                f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})"
            )
            await state.set_state(UserStates.idle)
            return
        
        logger.info(f"🎨 AIMage: {prompt[:50]}...")
        
        # Генерируем с FLUX.1-schnell
        result_image = await generate_with_flux_schnell(
            prompt=prompt,
            width=1024,
            height=1024,
            steps=4,
            guidance=3.5
        )
        
        if result_image:
            caption = (
                f"🎨 **Генерация завершена!**\n\n"
                f"📝 Промпт: `{prompt}`\n"
                f"✨ Создано с AI PhotoStudio 2.0 + FLUX.1-schnell"
            )
            
            await send_photo(
                message,
                BufferedInputFile(result_image, filename="ai_image.jpg"),
                caption=caption,
                reply_markup=get_main_menu()
            )
            
            usage.record_generation(user_id)
            logger.info(f"✅ AIMage completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")
    
    except Exception as e:
        logger.error(f"❌ AIMage error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    
    finally:
        await state.set_state(UserStates.idle)

# Статистика
@dp.callback_query(F.data == "stats")
async def handle_stats(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    usage_text = (
        f"📊 **Твоя статистика:**\n\n"
        f"📸 Создано сегодня: {usage.get_usage(user_id)}\n"
        f"🎯 Лимит в день: {usage.daily_limit}\n"
        f"📈 Осталось: {usage.daily_limit - usage.get_usage(user_id)}\n\n"
        f"⏰ Лимит обновится в 00:00 по МСК"
    )
    await callback.message.edit_text(usage_text, reply_markup=get_back_menu(), parse_mode="Markdown")

# Назад в главное меню
@dp.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.idle)
    await callback.message.edit_text(
        "🎨 **AI PhotoStudio 2.0**\n\n"
        "✨ *Профессиональные фотографии с ИИ*\n\n"
        "🎯 **3 категории:**\n"
        "📸 **AI Photoshoot** - реалистичные фото с твоим лицом\n"
        "🎨 **AI Styles** - популярные стили с референсом\n"
        "🎯 **AIMage** - генерация по промпту\n\n"
        f"💡 *Лимит: {usage.daily_limit} фото в день!*\n"
        "🚀 *FLUX.2-klein и FLUX.1-schnell технологии!*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# Запуск бота
async def main():
    await bot.delete_webhook()
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запуск для Railway
    uvicorn.run(
        "main_hf:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False
    )
