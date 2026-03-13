#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime
import io

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, ReplyKeyboardRemove, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from PIL import Image

import config
from services.cloudflare import (
    generate_photoshoot,
    generate_style,
    generate_ai_image
)
from services import UsageTracker
from states import UserStates
from keyboards import (
    get_main_menu,
    get_photoshoot_styles_keyboard,
    get_ai_styles_keyboard,
    get_photoshoot_formats_keyboard,
    get_ready_reply_keyboard,
)
from prompts import (
    PHOTOSHOOT_REALISM,
    AI_STYLES,
    PHOTOSHOOT_FORMATS,
    build_photoshoot_prompt,
    build_ai_styles_prompt
)

# Константы и настройки (без изменений)
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = config.BOT_TOKEN
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
usage = UsageTracker()

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

async def send_photo(message: types.Message, photo: BufferedInputFile, caption: str, reply_markup=None):
    # ... (без изменений, как в предыдущих версиях)
    pass

# ================== ОБРАБОТЧИКИ КОМАНД ==================

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
        "🚀 *FLUX.2 и FLUX.1 технологии!*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

# ================== НАЧАЛО СБОРА ФОТО ==================

@dp.callback_query(F.data == "ai_photoshoot")
async def handle_ai_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_photoshoot_face)
    await state.update_data(photoshoot_faces=[])
    await callback.message.edit_text(
        "📸 **AI Photoshoot - Фотореализм**\n\n"
        "🎯 Создаю профессиональные фотографии с твоим лицом\n"
        "💡 *Можно отправить до 4 фото для лучшего результата!*\n"
        "📸 *Отправляй фото по одному*\n\n"
        "👇 **После отправки всех фото нажми кнопку внизу**",
        parse_mode="Markdown"
    )
    await callback.message.answer(
        "📤 Отправляй фото (до 4). Когда закончишь, нажми кнопку внизу.",
        reply_markup=get_ready_reply_keyboard()
    )

@dp.callback_query(F.data == "ai_styles")
async def handle_ai_styles(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_ai_styles_face)
    await state.update_data(ai_styles_faces=[])
    await callback.message.edit_text(
        "🎨 **AI Styles - Популярные стили 2026**\n\n"
        "🎯 Создаю изображения с твоим лицом в разных стилях\n"
        "💡 *Можно отправить до 4 фото для лучшего результата!*\n"
        "📸 *Отправляй фото по одному*\n\n"
        "👇 **После отправки всех фото нажми кнопку внизу**",
        parse_mode="Markdown"
    )
    await callback.message.answer(
        "📤 Отправляй фото (до 4). Когда закончишь, нажми кнопку внизу.",
        reply_markup=get_ready_reply_keyboard()
    )

# ================== ОБРАБОТКА ЗАГРУЖЕННЫХ ФОТО ==================

@dp.message(F.photo)
async def handle_photo_upload(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    user_id = message.from_user.id

    if current_state == UserStates.waiting_for_photoshoot_face:
        data = await state.get_data()
        faces = data.get("photoshoot_faces", [])
        if len(faces) >= 4:
            await message.answer("❌ Ты уже отправил максимальное количество фото (4). Нажми «✅ Готово» для продолжения.")
            return
        photo_file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(photo_file.file_path)
        faces.append(photo_bytes.read())
        await state.update_data(photoshoot_faces=faces)
        logger.info(f"📸 AI Photoshoot: пользователь {user_id} отправил фото {len(faces)}/4")
        if len(faces) == 4:
            await message.answer(
                f"✅ Получено {len(faces)} фото. Переходим к выбору стиля.",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(UserStates.selecting_photoshoot_style)
            await message.answer(
                "📸 **Выбери стиль фотосессии**",
                reply_markup=get_photoshoot_styles_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"✅ Фото {len(faces)}/4 получено. Можешь отправить ещё или нажать «✅ Готово».",
                reply_markup=get_ready_reply_keyboard()
            )

    elif current_state == UserStates.waiting_for_ai_styles_face:
        # аналогично
        data = await state.get_data()
        faces = data.get("ai_styles_faces", [])
        if len(faces) >= 4:
            await message.answer("❌ Ты уже отправил максимальное количество фото (4). Нажми «✅ Готово» для продолжения.")
            return
        photo_file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(photo_file.file_path)
        faces.append(photo_bytes.read())
        await state.update_data(ai_styles_faces=faces)
        logger.info(f"🎨 AI Styles: пользователь {user_id} отправил фото {len(faces)}/4")
        if len(faces) == 4:
            await message.answer(
                f"✅ Получено {len(faces)} фото. Переходим к выбору стиля.",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(UserStates.selecting_ai_styles_style)
            await message.answer(
                "🎨 **Выбери стиль**",
                reply_markup=get_ai_styles_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"✅ Фото {len(faces)}/4 получено. Можешь отправить ещё или нажать «✅ Готово».",
                reply_markup=get_ready_reply_keyboard()
            )

# ================== ОБРАБОТКА КНОПКИ "ГОТОВО" (ТОЛЬКО ДЛЯ СБОРА ФОТО) ==================

@dp.message(F.text == "✅ Готово")
async def handle_ready_button_collection(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    # Если состояние не соответствует сбору фото – игнорируем (пусть обрабатывается в текстовом хендлере)
    if current_state not in [UserStates.waiting_for_photoshoot_face, UserStates.waiting_for_ai_styles_face]:
        return

    if current_state == UserStates.waiting_for_photoshoot_face:
        data = await state.get_data()
        faces = data.get("photoshoot_faces", [])
        if not faces:
            await message.answer("❌ Ты не отправил ни одного фото. Отправь хотя бы одно.")
            return
        await message.answer(
            f"✅ Завершён сбор фото (получено {len(faces)}). Переходим к выбору стиля.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(UserStates.selecting_photoshoot_style)
        await message.answer(
            "📸 **Выбери стиль фотосессии**",
            reply_markup=get_photoshoot_styles_keyboard(),
            parse_mode="Markdown"
        )

    elif current_state == UserStates.waiting_for_ai_styles_face:
        data = await state.get_data()
        faces = data.get("ai_styles_faces", [])
        if not faces:
            await message.answer("❌ Ты не отправил ни одного фото. Отправь хотя бы одно.")
            return
        await message.answer(
            f"✅ Завершён сбор фото (получено {len(faces)}). Переходим к выбору стиля.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(UserStates.selecting_ai_styles_style)
        await message.answer(
            "🎨 **Выбери стиль**",
            reply_markup=get_ai_styles_keyboard(),
            parse_mode="Markdown"
        )

# ================== ВЫБОР СТИЛЯ И ФОРМАТА ==================

@dp.callback_query(F.data.startswith("photoshoot_style_"))
async def handle_photoshoot_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_")[2]
    if style_key not in PHOTOSHOOT_REALISM:
        await callback.answer("❌ Стиль не найден", show_alert=True)
        return
    style = PHOTOSHOOT_REALISM[style_key]
    await state.update_data(photoshoot_style=style_key)
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

@dp.callback_query(F.data.startswith("photoshoot_format_"))
async def handle_photoshoot_format(callback: types.CallbackQuery, state: FSMContext):
    format_key = "_".join(callback.data.split("_")[2:])
    if format_key not in PHOTOSHOOT_FORMATS:
        await callback.answer("❌ Формат не найден", show_alert=True)
        return
    format_info = PHOTOSHOOT_FORMATS[format_key]
    await state.update_data(photoshoot_format=format_key)
    await state.set_state(UserStates.waiting_for_photoshoot_prompt)

    await callback.message.edit_text(
        f"📐 **{format_info['name']}**\n\n"
        f"📝 {format_info['description']}\n\n"
        f"✍️ **Добавь детали для генерации:**\n"
        f"• Где находится?\n"
        f"• Во что одет?\n"
        f"• Какое настроение?\n\n"
        f"👇 Напиши детали или нажми кнопку внизу",
        parse_mode="Markdown"
    )
    await callback.message.answer(
        "📝 Введи детали или нажми «✅ Готово», чтобы использовать базовый стиль.",
        reply_markup=get_ready_reply_keyboard()
    )

@dp.callback_query(F.data.startswith("ai_style_"))
async def handle_ai_styles_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_")[2]
    if style_key not in AI_STYLES:
        await callback.answer("❌ Стиль не найден", show_alert=True)
        return
    style = AI_STYLES[style_key]
    await state.update_data(ai_styles_style=style_key)
    await state.set_state(UserStates.waiting_for_ai_styles_prompt)

    await callback.message.edit_text(
        f"🎨 **{style['name']}**\n\n"
        f"📝 {style['description']}\n\n"
        f"✍️ **Добавь детали для генерации:**\n"
        f"• Что еще добавить?\n"
        f"• Какое настроение?\n\n"
        f"👇 Напиши детали или нажми кнопку внизу",
        parse_mode="Markdown"
    )
    await callback.message.answer(
        "📝 Введи детали или нажми «✅ Готово», чтобы использовать базовый стиль.",
        reply_markup=get_ready_reply_keyboard()
    )

# ================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ (ПРОМПТЫ) ==================

# ================== ЕДИНЫЙ ОБРАБОТЧИК ТЕКСТА ==================
@dp.message()
async def handle_text_messages(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    user_text = message.text.strip()
    
    # Логируем для отладки (убедимся, что сообщение пришло)
    logger.info(f"📩 Текстовое сообщение: '{user_text}' в состоянии {current_state}")

    # ---- Этап сбора фото (кнопка "✅ Готово") ----
    if current_state == UserStates.waiting_for_photoshoot_face:
        if user_text == "✅ Готово":
            data = await state.get_data()
            faces = data.get("photoshoot_faces", [])
            if not faces:
                await message.answer("❌ Ты не отправил ни одного фото. Отправь хотя бы одно.")
                return
            await message.answer(
                f"✅ Завершён сбор фото (получено {len(faces)}). Переходим к выбору стиля.",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(UserStates.selecting_photoshoot_style)
            await message.answer(
                "📸 **Выбери стиль фотосессии**",
                reply_markup=get_photoshoot_styles_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer("Отправляй фото или нажми «✅ Готово».")
        return

    if current_state == UserStates.waiting_for_ai_styles_face:
        if user_text == "✅ Готово":
            data = await state.get_data()
            faces = data.get("ai_styles_faces", [])
            if not faces:
                await message.answer("❌ Ты не отправил ни одного фото. Отправь хотя бы одно.")
                return
            await message.answer(
                f"✅ Завершён сбор фото (получено {len(faces)}). Переходим к выбору стиля.",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.set_state(UserStates.selecting_ai_styles_style)
            await message.answer(
                "🎨 **Выбери стиль**",
                reply_markup=get_ai_styles_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await message.answer("Отправляй фото или нажми «✅ Готово».")
        return

    # ---- Этап ввода промпта (AI Photoshoot) ----
    if current_state == UserStates.waiting_for_photoshoot_prompt:
        if user_text == "✅ Готово":
            logger.info("✅ Нажата кнопка 'Готово' без текста – запускаем генерацию с базовым промптом")
            await process_photoshoot_generation(message, state, custom_prompt="")
        else:
            logger.info(f"📝 Получен текст промпта: {user_text}")
            await state.update_data(photoshoot_prompt=user_text)
            await process_photoshoot_generation(message, state, custom_prompt=user_text)
        return

    # ---- Этап ввода промпта (AI Styles) ----
    if current_state == UserStates.waiting_for_ai_styles_prompt:
        if user_text == "✅ Готово":
            logger.info("✅ Нажата кнопка 'Готово' без текста – запускаем генерацию с базовым промптом")
            await process_ai_styles_generation(message, state, custom_prompt="")
        else:
            logger.info(f"📝 Получен текст промпта: {user_text}")
            await state.update_data(ai_styles_prompt=user_text)
            await process_ai_styles_generation(message, state, custom_prompt=user_text)
        return

    # ---- Этап ввода промпта (AIMage) ----
    if current_state == UserStates.waiting_for_ai_image_prompt:
        if user_text == "✅ Готово":
            logger.info("✅ Нажата кнопка 'Готово' без текста – запускаем генерацию с базовым промптом")
            await process_ai_image_generation(message, state, custom_prompt="")
        else:
            logger.info(f"📝 Получен текст промпта: {user_text}")
            await state.update_data(ai_image_prompt=user_text)
            await process_ai_image_generation(message, state, custom_prompt=user_text)
        return

    # ---- Если сообщение не обработано - игнорируем (но логируем)
    logger.info(f"⚠️ Сообщение не обработано: '{user_text}' в состоянии {current_state}")


# ================== ФУНКЦИИ ГЕНЕРАЦИИ ==================

async def process_photoshoot_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    await state.set_state(UserStates.generating_photoshoot)
    await message.answer("📸 *Генерирую изображение...*", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

    try:
        data = await state.get_data()
        face_photos = data.get("photoshoot_faces", [])
        style_key = data.get("photoshoot_style", "portrait")
        format_key = data.get("photoshoot_format", "vertical_4_3")
        user_prompt = custom_prompt or data.get("photoshoot_prompt", "")

        if not face_photos:
            await message.answer("❌ Фото не найдено. Начни заново")
            await state.set_state(UserStates.idle)
            return

        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})")
            await state.set_state(UserStates.idle)
            return

        format_info = PHOTOSHOOT_FORMATS[format_key]
        final_prompt = build_photoshoot_prompt(style_key, "selfie", user_prompt)

        logger.info(f"📸 AI Photoshoot: {style_key} - {final_prompt[:100]}...")
        logger.info(f"📸 Используется {len(face_photos)} референсных фото")

        image_bytes = await generate_photoshoot(
            prompt=final_prompt,
            reference_images=face_photos,
            width=format_info["width"],
            height=format_info["height"],
            guidance=7.5
        )

        if image_bytes:
            style = PHOTOSHOOT_REALISM[style_key]
            caption = (
                f"📸 **{style['name']} готов!**\n\n"
                f"📐 Формат: {format_info['name']}\n"
                f"📝 Детали: `{user_prompt if user_prompt else 'Базовый стиль'}`\n"
                f"✨ Создано с AI PhotoStudio 2.0 + FLUX.2-klein"
            )
            await send_photo(message, BufferedInputFile(image_bytes, "photoshoot.jpg"), caption, get_main_menu())
            usage.record_generation(user_id)
            logger.info(f"✅ AI Photoshoot completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")

    except Exception as e:
        logger.exception("❌ Полная ошибка в AI Photoshoot:")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    finally:
        await state.set_state(UserStates.idle)

async def process_ai_styles_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    await state.set_state(UserStates.generating_ai_styles)
    await message.answer("🎨 *Генерирую изображение...*", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

    try:
        data = await state.get_data()
        face_photos = data.get("ai_styles_faces", [])
        style_key = data.get("ai_styles_style", "cyberpunk")
        user_prompt = custom_prompt or data.get("ai_styles_prompt", "")

        if not face_photos:
            await message.answer("❌ Фото не найдено. Начни заново")
            await state.set_state(UserStates.idle)
            return

        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})")
            await state.set_state(UserStates.idle)
            return

        final_prompt = build_ai_styles_prompt(style_key, user_prompt)
        logger.info(f"🎨 AI Styles: {style_key} - {final_prompt[:100]}...")
        logger.info(f"🎨 Используется {len(face_photos)} референсных фото")

        image_bytes = await generate_style(
            prompt=final_prompt,
            reference_images=face_photos,
            width=1024,
            height=576,
            guidance=7.5
        )

        if image_bytes:
            style = AI_STYLES[style_key]
            caption = (
                f"🎨 **{style['name']} готов!**\n\n"
                f"📝 Детали: `{user_prompt if user_prompt else 'Базовый стиль'}`\n"
                f"📐 Формат: 16:9\n"
                f"✨ Создано с AI PhotoStudio 2.0 + FLUX.2-klein"
            )
            await send_photo(message, BufferedInputFile(image_bytes, "ai_styles.jpg"), caption, get_main_menu())
            usage.record_generation(user_id)
            logger.info(f"✅ AI Styles completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")

    except Exception as e:
        logger.exception("❌ Полная ошибка в AI Styles:")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    finally:
        await state.set_state(UserStates.idle)

async def process_ai_image_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    await state.set_state(UserStates.generating_ai_image)
    await message.answer("🎨 *Генерирую изображение...*", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

    try:
        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})")
            await state.set_state(UserStates.idle)
            return

        data = await state.get_data()
        prompt = custom_prompt or data.get("ai_image_prompt", "")
        if not prompt.strip():
            prompt = "beautiful digital art, high quality, detailed, vibrant colors, professional illustration"

        logger.info(f"🎨 AIMage: {prompt[:50]}...")

        image_bytes = await generate_ai_image(
            prompt=prompt,
            width=1024,
            height=1024,
            steps=4,
            guidance=3.5
        )

        if image_bytes:
            caption = (
                f"🎨 **Генерация завершена!**\n\n"
                f"📝 Промпт: `{prompt}`\n"
                f"✨ Создано с AI PhotoStudio 2.0 + FLUX.1-schnell"
            )
            await send_photo(message, BufferedInputFile(image_bytes, "ai_image.jpg"), caption, get_main_menu())
            usage.record_generation(user_id)
            logger.info(f"✅ AIMage completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")

    except Exception as e:
        logger.exception("❌ Полная ошибка в AIMage:")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    finally:
        await state.set_state(UserStates.idle)

# ================== ЗАПУСК ==================

if __name__ == "__main__":
    use_webhook = os.getenv("USE_WEBHOOK", "true").lower() == "true"
    if use_webhook:
        async def on_startup(app):
            public_url = os.getenv("PUBLIC_URL", "").rstrip('/')
            webhook_path = config.WEBHOOK_PATH
            if public_url:
                webhook_url = f"{public_url}{webhook_path}"
                await bot.set_webhook(webhook_url)
                logger.info(f"✅ Вебхук автоматически установлен: {webhook_url}")
            else:
                logger.warning("⚠️ PUBLIC_URL не задан, вебхук не установлен.")

        async def on_shutdown(app):
            logger.info("⏹️ Приложение остановлено")

        app = web.Application()
        async def handle_webhook(request):
            try:
                data = await request.json()
                from aiogram.types import Update
                update = Update(**data)
                await dp.feed_update(bot, update)
                return web.Response(text="OK")
            except Exception as e:
                logger.exception("❌ Webhook error:")
                return web.Response(text="Error", status=500)

        app.router.add_post(config.WEBHOOK_PATH, handle_webhook)
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)
        port = int(os.getenv("PORT", 8000))
        logger.info(f"🚀 Запуск сервера на порту {port}")
        web.run_app(app, host="0.0.0.0", port=port)
    else:
        logger.info("🔄 Запуск в режиме polling")
        asyncio.run(dp.start_polling(bot))
