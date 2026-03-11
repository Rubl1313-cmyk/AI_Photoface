# 🚀 AI PhotoStudio 3.0 - Финальная версия
# Ультра-реалистичный бот с реальными моделями Cloudflare

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
from aiogram.types import BufferedInputFile, ReplyKeyboardRemove
from fastapi import FastAPI
import uvicorn
import httpx
import base64
import io
import json

import config
from services.phoenix_cloudflare import generate_with_phoenix, generate_with_lucid, generate_photoshoot_with_face
from services.usage import UsageTracker
from modern_states import UserStates
from modern_keyboards import get_modern_main_menu, get_photoshoot_styles_keyboard

# Константы
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

# HuggingFace FaceFusion API
FACEFUSION_URL = os.getenv("FACEFUSION_URL", "https://your-space.hf.space")

# Ультра-реалистичные стили фотосессий
ULTRA_PHOTOSHOOT_STYLES = {
    "ultra_business": {
        "name": "💼 Ultra Бизнес-портрет",
        "base_prompt": "ultra realistic professional business portrait, executive pose, confident expression, perfect lighting, high-end business attire, corporate environment",
        "examples": ["in modern glass office", "with city skyline background", "with professional lighting setup", "in boardroom setting"],
        "description": "Максимальное качество для LinkedIn и резюме",
        "model": "lucid"  # Lucid для фотореализма
    },
    "ultra_fashion": {
        "name": "👗 Ultra Мода-портрет", 
        "base_prompt": "ultra realistic high fashion portrait, model pose, dramatic studio lighting, designer clothing, vogue style photography, perfect skin texture",
        "examples": ["on fashion runway", "in high-end studio", "with dramatic lighting", "couture fashion shoot"],
        "description": "Качество глянцевого журнала",
        "model": "lucid"  # Lucid для фотореализма
    },
    "ultra_casual": {
        "name": "🌴 Ultra Повседневный стиль",
        "base_prompt": "ultra realistic casual portrait, natural authentic expression, perfect natural lighting, lifestyle photography, street style, detailed textures",
        "examples": ["in urban cafe", "in city park", "natural outdoor lighting", "lifestyle photography"],
        "description": "Естественный look для соцсетей",
        "model": "lucid"  # Lucid для фотореализма
    },
    "ultra_creative": {
        "name": "🎨 Ultra Креативный портрет",
        "base_prompt": "ultra realistic creative portrait, artistic expression, unique lighting setup, conceptual photography, dramatic shadows, perfect composition",
        "examples": ["with neon lighting", "in abstract environment", "artistic concept", "creative photography"],
        "description": "Для творческих проектов",
        "model": "phoenix"  # Phoenix для креативности
    },
    "ultra_sport": {
        "name": "🏃 Ultra Спортивный портрет",
        "base_prompt": "ultra realistic athletic portrait, dynamic pose, fitness photography, perfect muscle definition, professional sports lighting, detailed skin texture",
        "examples": ["in modern gym", "outdoor action shot", "fitness photography", "dynamic sports pose"],
        "description": "Энергичный образ с детализацией",
        "model": "lucid"  # Lucid для фотореализма
    },
    "ultra_luxury": {
        "name": "💎 Ultra Роскошный портрет",
        "base_prompt": "ultra realistic luxury portrait, elegant sophisticated pose, premium lighting, high-end fashion, luxury environment, perfect skin details",
        "examples": ["in luxury hotel", "on private yacht", "premium setting", "high-end lifestyle"],
        "description": "Элитный образ максимального качества",
        "model": "lucid"  # Lucid для фотореализма
    }
}

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=config.TG_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
usage = UsageTracker(daily_limit=100, data_dir=DATA_DIR)

# FastAPI для Railway
app = FastAPI(title="AI PhotoStudio API", version="2.0.0")

# Класс для работы с HuggingFace FaceFusion
class HuggingFaceFusionClient:
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")
        logger.info(f"🤗 HuggingFace FaceFusion initialized: {self.api_url}")
    
    async def swap_face_hf(self, source_image: bytes, target_image: bytes, 
                         face_enhancer: bool = True,
                         face_swapper_model: str = "inswapper_128",
                         face_enhancer_model: str = "gfpgan_1.4") -> bytes:
        """Замена лица через HuggingFace FaceFusion"""
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                # Подготовка файлов
                files = {
                    "target": ("target.jpg", target_image, "image/jpeg"),
                    "source": ("source.jpg", source_image, "image/jpeg")
                }
                
                data = {
                    "face_enhancer": "true" if face_enhancer else "false",
                    "face_swapper_model": face_swapper_model,
                    "face_enhancer_model": face_enhancer_model
                }
                
                logger.info(f"🔄 HuggingFace FaceFusion request")
                
                response = await client.post(
                    f"{self.api_url}/swap",
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result_bytes = response.content
                    logger.info(f"✅ HuggingFace swap success: {len(result_bytes)} bytes")
                    
                    # Дополнительная обработка
                    enhanced_bytes = self._enhance_result(result_bytes)
                    return enhanced_bytes
                else:
                    logger.error(f"❌ HuggingFace error {response.status_code}: {response.text[:200]}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("❌ HuggingFace timeout after 300s")
            return None
        except Exception as e:
            logger.error(f"❌ HuggingFace error: {e}")
            return None
    
    async def enhance_face_only_hf(self, image: bytes, 
                              enhancer_model: str = "gfpgan_1.4") -> bytes:
        """Улучшение только лица через HuggingFace"""
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                files = {"image": ("image.jpg", image, "image/jpeg")}
                data = {"enhancer_model": enhancer_model}
                
                response = await client.post(
                    f"{self.api_url}/enhance",
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result_bytes = response.content
                    enhanced_bytes = self._enhance_result(result_bytes)
                    logger.info(f"✅ HuggingFace enhancement success: {len(enhanced_bytes)} bytes")
                    return enhanced_bytes
                else:
                    logger.error(f"❌ HuggingFace enhancement error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ HuggingFace enhancement error: {e}")
            return None
    
    def _enhance_result(self, image_bytes: bytes) -> bytes:
        """Дополнительная обработка результата"""
        try:
            from PIL import Image, ImageEnhance, ImageFilter
            import io
            
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            # Улучшение резкости
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.2)
            
            # Улучшение контрастности
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            
            # Unsharp mask
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
            
            # Сохранение
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=98, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"❌ Enhancement error: {e}")
            return image_bytes

# Инициализация HuggingFace FaceFusion
facefusion_client = HuggingFaceFusionClient(FACEFUSION_URL)

# Вспомогательные функции
async def send_message(event, text: str, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        return await event.message.answer(text, reply_markup=reply_markup)
    else:
        return await event.reply(text, reply_markup=reply_markup)

async def send_photo(event, photo, caption: str = None, reply_markup=None):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        return await event.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    else:
        return await event.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup)

# FastAPI эндпоинты
@app.get("/")
async def root():
    return {
        "status": "running", 
        "service": "AI PhotoStudio 2.0", 
        "face_swap": "HuggingFace FaceFusion",
        "daily_limit": "100 photos"
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: dict):
    """Вебхук для Telegram"""
    try:
        update = types.Update(**request)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return {"ok": False, "error": str(e)}

# Обработчики бота
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.idle)
    
    await message.answer("🎨 **AI PhotoStudio 2.0 - HuggingFace Edition**", reply_markup=ReplyKeyboardRemove())
    
    await message.answer(
        "✨ *Профессиональные фотографии с ИИ*\n\n"
        "🎯 **Новые возможности:**\n"
        "📸 **AI Фотосессия** - твоё лицо + твои промпты\n"
        "🎨 **Генерация** - создай любую картинку\n"
        "🔄 **Замена лица** - HuggingFace FaceFusion\n\n"
        f"💡 *Лимит: {usage.daily_limit} фото в день!*\n"
        "🚀 *Использует лучшие модели: Phoenix, Lucid, FaceFusion!*",
        reply_markup=get_modern_main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "photoshoot")
async def handle_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_face_photoshoot)
    await callback.message.edit_text(
        "📸 **AI Фотосессия с твоими промптами**\n\n"
        "🎯 Создам профессиональные фотографии с твоим лицом\n"
        "💡 *С HuggingFace FaceFusion для максимального качества!*\n\n"
        "👇 *Отправь своё фото* (хорошего качества, лицо видно четко)",
        parse_mode="Markdown"
    )

@dp.message(F.photo)
async def handle_photo_for_photoshoot(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == UserStates.waiting_for_face_photoshoot:
        # Сохраняем фото
        photo_file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(photo_file.file_path)
        
        await state.update_data(face_photo=photo_bytes.read())
        
        # Показываем стили фотосессий
        await state.set_state(UserStates.selecting_photoshoot_style)
        await message.answer(
            "🎨 **Выбери стиль фотосессии**\n\n"
            "💡 *После выбора сможешь добавить свои детали*",
            reply_markup=get_photoshoot_styles_keyboard(),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data.startswith("ultra_style_"))
async def handle_photoshoot_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_")[2]
    
    if style_key not in ULTRA_PHOTOSHOOT_STYLES:
        await callback.answer("❌ Стиль не найден", show_alert=True)
        return
    
    style = ULTRA_PHOTOSHOOT_STYLES[style_key]
    await state.update_data(ultra_photoshoot_style=style_key)
    
    # Показываем примеры и запрашиваем пользовательский промпт
    examples_text = "\n".join([f"• {ex}" for ex in style["examples"]])
    
    await state.set_state(UserStates.waiting_for_custom_prompt)
    await callback.message.edit_text(
        f"🎨 **{style['name']}**\n\n"
        f"📝 {style['description']}\n\n"
        f"💡 **Примеры промптов:**\n{examples_text}\n\n"
        f"✍️ *Теперь добавь свои детали:*\n"
        f"• Где находится? (на крыше, в кафе, на пляже)\n"
        f"• Во что одет? (в джинсах, в вечернем платье)\n"
        f"• Какая поза? (сидит, стоит, идет)\n"
        f"• Какое настроение? (счастливый, задумчивый)\n\n"
        f"👇 *Напиши свой промпт или отправь 'готово'*",
        parse_mode="Markdown"
    )

@dp.message()
async def handle_custom_prompt(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    user_prompt = message.text.strip().lower()
    
    if current_state == UserStates.waiting_for_custom_prompt:
        if user_prompt in ['готово', 'дальше', 'continue']:
            await process_photoshoot_generation(message, state, "")
        else:
            await state.update_data(custom_prompt=message.text.strip())
            await message.answer(
                "✅ *Промпт добавлен!*\n\n"
                "👇 *Отправь 'готово' для генерации или добавь еще деталей*",
                parse_mode="Markdown"
            )

async def process_photoshoot_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    """Обработка генерации фотосессии с HuggingFace FaceFusion"""
    await state.set_state(UserStates.generating_photoshoot)
    await message.answer("🎨 *Создаю профессиональные фотографии...*", parse_mode="Markdown")
    
    try:
        data = await state.get_data()
        face_photo = data.get("face_photo")
        style_key = data.get("ultra_photoshoot_style", "ultra_casual")
        user_prompt = custom_prompt or data.get("custom_prompt", "")
        
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
        style = ULTRA_PHOTOSHOOT_STYLES[style_key]
        base_prompt = style["base_prompt"]
        
        if user_prompt:
            final_prompt = f"{base_prompt}, {user_prompt}"
        else:
            final_prompt = base_prompt
        
        enhanced_prompt = f"{final_prompt}, professional photography, ultra realistic, sharp focus, natural lighting, high quality, detailed"
        
        logger.info(f"📸 Photoshoot: {style_key} - {enhanced_prompt[:100]}...")
        
        # Генерируем с Lucid (лучший для фотореализма)
        result_image = await generate_photoshoot_with_face(
            prompt=enhanced_prompt,
            source_image_bytes=face_photo,
            model="lucid",
            width=1024,
            height=1024,
            steps=25,
            guidance=7.0,
            strength=0.85
        )
        
        if result_image:
            # Дополнительная обработка через HuggingFace FaceFusion
            try:
                enhanced_face = await facefusion_client.enhance_face_only_hf(result_image)
                if enhanced_face:
                    result_image = enhanced_face
                    logger.info("✅ HuggingFace FaceFusion enhancement applied")
            except Exception as e:
                logger.warning(f"⚠️ HuggingFace enhancement failed: {e}")
            
            caption = (
                f"📸 **{style['name']} готов!**\n\n"
                f"📝 Промпт: `{user_prompt if user_prompt else 'Базовый стиль'}`\n"
                f"✨ Создано с AI PhotoStudio 2.0 + HuggingFace"
            )
            
            await send_photo(
                message,
                BufferedInputFile(result_image, filename="photoshoot.jpg"),
                caption=caption,
                reply_markup=get_modern_main_menu()
            )
            
            usage.record_generation(user_id)
            logger.info(f"✅ Photoshoot completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")
    
    except Exception as e:
        logger.error(f"❌ Photoshoot error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    
    finally:
        await state.set_state(UserStates.idle)

@dp.callback_query(F.data == "swap")
async def handle_swap(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_target_swap)
    await callback.message.edit_text(
        "🔄 **Замена лица - HuggingFace FaceFusion**\n\n"
        "🎯 Профессиональная замена лиц с максимальным качеством\n"
        "💡 *Использует реальные модели FaceFusion!*\n\n"
        "👇 *Отправь фото, где нужно заменить лицо*\n\n"
        "💡 *Сначала сделай AI Фотосессию, чтобы я запомнил твоё лицо!*",
        parse_mode="Markdown"
    )

@dp.message(F.photo)
async def handle_target_swap(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == UserStates.waiting_for_target_swap:
        # Проверка лимита
        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(
                f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{usage.daily_limit})"
            )
            await state.set_state(UserStates.idle)
            return
        
        await state.set_state(UserStates.generating)
        await message.answer("🔄 *Заменяю лицо через HuggingFace...*", parse_mode="Markdown")
        
        try:
            # Получаем фото
            photo_file = await bot.get_file(message.photo[-1].file_id)
            target_bytes = await bot.download_file(photo_file.file_path)
            
            # Получаем сохраненное фото лица (должно быть в состоянии)
            state_data = await state.get_data()
            face_photo = state_data.get("face_photo")
            
            if not face_photo:
                await message.answer(
                    "❌ *Сначала сделай AI Фотосессию!*\n\n"
                    "Мне нужно запомнить твоё лицо для замены.\n"
                    "💡 Сделай фотосессию, потом возвращайся сюда.",
                    reply_markup=get_modern_main_menu(),
                    parse_mode="Markdown"
                )
                await state.set_state(UserStates.idle)
                return
            
            # Замена лица через HuggingFace
            result_image = await facefusion_client.swap_face_hf(
                source_image=face_photo,
                target_image=target_bytes,
                face_enhancer=True,
                face_swapper_model="inswapper_128",
                face_enhancer_model="gfpgan_1.4"
            )
            
            if result_image:
                caption = (
                    f"🔄 **Замена лица завершена!**\n\n"
                    f"✨ Создано с HuggingFace FaceFusion\n"
                    f"🎯 Качество: Профессиональное"
                )
                
                await send_photo(
                    message,
                    BufferedInputFile(result_image, filename="face_swap.jpg"),
                    caption=caption,
                    reply_markup=get_modern_main_menu()
                )
                
                usage.record_generation(user_id)
                logger.info(f"✅ Face swap completed for user {user_id}")
            else:
                await message.answer("❌ Ошибка замены лица. Попробуй ещё раз")
        
        except Exception as e:
            logger.error(f"❌ Swap error: {e}")
            await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
        
        finally:
            await state.set_state(UserStates.idle)

if __name__ == "__main__":
    # Запуск для Railway
    uvicorn.run(
        "main_hf:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False
    )
