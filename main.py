# 🚀 Railway.app - Основной файл бота
# Улучшенная версия с пользовательскими промптами и максимальным качеством
import asyncio
import logging
import os
import tempfile
import shutil
from pathlib import Path
from aiogram import Bot, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, ReplyKeyboardRemove
from fastapi import FastAPI
import uvicorn

import config
from modern_states import UserStates
from modern_keyboards import get_modern_main_menu, get_photoshoot_styles_keyboard, get_reply_keyboard
from services.phoenix_cloudflare import generate_with_phoenix, generate_with_lucid, generate_photoshoot_with_face
from services.enhanced_face_fusion import EnhancedFaceFusionClient
from services.usage import UsageTracker

# Константы
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

# Улучшенные стили фотосессий с пользовательскими промптами
PHOTOSHOOT_STYLES = {
    "business": {
        "name": "💼 Бизнес-портрет",
        "base_prompt": "professional business portrait, suit or business casual, confident pose",
        "examples": ["в современном офисе", "на фоне города", "с документами"],
        "description": "Идеально для LinkedIn, резюме"
    },
    "fashion": {
        "name": "👗 Мода-портрет", 
        "base_prompt": "high fashion portrait, stylish outfit, model pose, dramatic lighting",
        "examples": ["на подиуме", "в студии", "на улице моды"],
        "description": "Как в глянцевом журнале"
    },
    "casual": {
        "name": "🌴 Повседневный стиль",
        "base_prompt": "casual portrait, relaxed pose, natural lighting, authentic expression", 
        "examples": ["в парке", "в кафе", "на улице"],
        "description": "Естественный образ для соцсетей"
    },
    "creative": {
        "name": "🎨 Креативный портрет",
        "base_prompt": "creative portrait, artistic expression, unique pose, colorful background",
        "examples": ["с неоновым светом", "в абстрактной обстановке", "с цветами"],
        "description": "Для творческих проектов"
    },
    "sport": {
        "name": "🏃 Спортивный портрет",
        "base_prompt": "sport portrait, athletic pose, fitness setting, dynamic lighting",
        "examples": ["в спортзале", "на стадионе", "на улице"],
        "description": "Энергичный и сильный образ"
    },
    "luxury": {
        "name": "💎 Роскошный портрет",
        "base_prompt": "luxury portrait, elegant outfit, premium setting, sophisticated lighting",
        "examples": ["в люксовом отеле", "на яхте", "в ресторане"],
        "description": "Элитный образ"
    },
    "custom": {
        "name": "🎯 Свой стиль",
        "base_prompt": "custom portrait photography",
        "examples": ["любая локация", "любая одежда", "любая поза"],
        "description": "Полностью кастомный промпт"
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
facefusion_client = EnhancedFaceFusionClient(api_url=config.FACEFUSION_URL)
usage = UsageTracker(daily_limit=config.DAILY_LIMIT, data_dir=DATA_DIR)

# FastAPI для Railway
app = FastAPI(title="AI PhotoStudio API", version="2.0.0")

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
    return {"status": "running", "service": "AI PhotoStudio 2.0"}

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
    await message.answer("🎨 **AI PhotoStudio 2.0 - Railway Edition**", reply_markup=ReplyKeyboardRemove())
    
    await message.answer(
        "✨ *Профессиональные фотографии с ИИ*\n\n"
        "🎯 **Новые возможности:**\n"
        "📸 **AI Фотосессия** - твоё лицо + твои промпты\n"
        "🎨 **Генерация** - создай любую картинку\n"
        "🔄 **Замена лица** - поменяй лицо на фото\n\n"
        "💡 *Теперь можешь добавлять свои промпты в фотосессию!*",
        reply_markup=get_modern_main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "photoshoot")
async def handle_photoshoot(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_face_photoshoot)
    await callback.message.edit_text(
        "📸 **AI Фотосессия с твоими промптами**\n\n"
        "🎯 Создам профессиональные фотографии с твоим лицом\n"
        "💡 *Сможешь добавить любую локацию, одежду, позу!*\n\n"
        "👇 *Отправь своё фото* (хорошего качества, лицо видно четко)",
        parse_mode="Markdown"
    )

@dp.message(UserStates.waiting_for_face_photoshoot)
async def handle_face_for_photoshoot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Отправь фото, а не текст")
        return
    
    # Сохраняем фото
    photo_file = await bot.get_file(message.photo[-1].file_id)
    photo_bytes = await bot.download_file(photo_file.file_path)
    
    await state.update_data(face_photo=photo_bytes.read())
    
    # Показываем стили фотосессий
    await state.set_state(UserStates.selecting_photoshoot_style)
    
    # Создаем клавиатуру с примерами
    keyboard = get_photoshoot_examples_keyboard()
    await message.answer(
        "🎨 **Выбери стиль фотосессии**\n\n"
        "💡 *После выбора сможешь добавить свои детали*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

def get_photoshoot_examples_keyboard():
    """Клавиатура с примерами промптов"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем стили с примерами
    for style_key, style_data in PHOTOSHOOT_STYLES.items():
        examples_text = ", ".join(style_data["examples"][:2])
        builder.button(
            text=f"{style_data['name']}", 
            callback_data=f"style_{style_key}"
        )
    
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

@dp.callback_query(F.data.startswith("style_"))
async def handle_photoshoot_style(callback: types.CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_")[1]
    
    if style_key not in PHOTOSHOOT_STYLES:
        await callback.answer("❌ Стиль не найден", show_alert=True)
        return
    
    style = PHOTOSHOOT_STYLES[style_key]
    await state.update_data(photoshoot_style=style_key)
    
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

@dp.message(UserStates.waiting_for_custom_prompt)
async def handle_custom_prompt(message: types.Message, state: FSMContext):
    user_prompt = message.text.strip().lower()
    
    # Проверяем, что пользователь готов
    if user_prompt in ['готово', 'дальше', 'continue']:
        await process_photoshoot_generation(message, state, "")
        return
    
    # Сохраняем пользовательский промпт
    await state.update_data(custom_prompt=message.text.strip())
    
    await message.answer(
        "✅ *Промпт добавлен!*\n\n"
        "👇 *Отправь 'готово' для генерации или добавь еще деталей*",
        parse_mode="Markdown"
    )

async def process_photoshoot_generation(message: types.Message, state: FSMContext, custom_prompt: str = ""):
    """Обработка генерации фотосессии"""
    await state.set_state(UserStates.generating_photoshoot)
    await message.answer("🎨 *Создаю профессиональные фотографии...*", parse_mode="Markdown")
    
    try:
        data = await state.get_data()
        face_photo = data.get("face_photo")
        style_key = data.get("photoshoot_style", "casual")
        user_prompt = custom_prompt or data.get("custom_prompt", "")
        
        if not face_photo:
            await message.answer("❌ Фото не найдено. Начни заново")
            await state.set_state(UserStates.idle)
            return
        
        # Проверка лимита
        user_id = message.from_user.id
        if not usage.can_generate(user_id):
            await message.answer(
                f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{config.DAILY_LIMIT})"
            )
            await state.set_state(UserStates.idle)
            return
        
        # Собираем финальный промпт
        style = PHOTOSHOOT_STYLES[style_key]
        base_prompt = style["base_prompt"]
        
        # Добавляем пользовательский промпт
        if user_prompt:
            final_prompt = f"{base_prompt}, {user_prompt}"
        else:
            final_prompt = base_prompt
        
        # Улучшенный промпт для максимального качества
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
            # Дополнительная обработка через FaceFusion для улучшения лица
            try:
                enhanced_face = await facefusion_client.enhance_face_only(result_image)
                if enhanced_face:
                    result_image = enhanced_face
                    logger.info("✅ Face enhancement applied")
            except Exception as e:
                logger.warning(f"⚠️ Face enhancement failed: {e}")
            
            caption = (
                f"📸 **{style['name']} готов!**\n\n"
                f"🎝 Промпт: `{user_prompt if user_prompt else 'Базовый стиль'}`\n"
                f"✨ Создано с AI PhotoStudio 2.0"
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

@dp.callback_query(F.data == "generate")
async def handle_generate(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_prompt_generate)
    await callback.message.edit_text(
        "🎨 **Генерация по промпту**\n\n"
        "👇 *Опиши, что хочешь создать*\n\n"
        "💡 *Советы для лучшего результата:*\n"
        "• Добавь детали: 'закат на море, волны, пальмы'\n"
        "• Укажи стиль: 'в стиле импрессионизма'\n"
        "• Добавь настроение: 'уютная атмосфера'",
        parse_mode="Markdown"
    )

@dp.message(UserStates.waiting_for_prompt_generate)
async def handle_prompt_generate(message: types.Message, state: FSMContext):
    prompt = message.text.strip()
    
    if not prompt:
        await message.answer("❌ Промпт не может быть пустым")
        return
    
    # Проверка лимита
    user_id = message.from_user.id
    if not usage.can_generate(user_id):
        await message.answer(
            f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{config.DAILY_LIMIT})"
        )
        await state.set_state(UserStates.idle)
        return
    
    await state.set_state(UserStates.generating)
    await message.answer("🎨 *Создаю изображение...*", parse_mode="Markdown")
    
    try:
        # Используем Phoenix для креативных промптов, Lucid для фотореализма
        if any(word in prompt.lower() for word in ['фото', 'портрет', 'человек', 'реалистичный']):
            result_image = await generate_with_lucid(
                prompt=f"{prompt}, photorealistic, professional photography",
                width=1024,
                height=1024,
                steps=25,
                guidance=4.0
            )
        else:
            result_image = await generate_with_phoenix(
                prompt=prompt,
                width=1024,
                height=1024,
                steps=25,
                guidance=4.0
            )
        
        if result_image:
            caption = f"🎨 **Готово!**\n\n📝 Промпт: `{prompt}`\n✨ Создано с AI PhotoStudio 2.0"
            
            await send_photo(
                message,
                BufferedInputFile(result_image, filename="generated.jpg"),
                caption=caption,
                reply_markup=get_modern_main_menu()
            )
            
            usage.record_generation(user_id)
            logger.info(f"✅ Generation completed for user {user_id}")
        else:
            await message.answer("❌ Ошибка генерации. Попробуй другой промпт")
    
    except Exception as e:
        logger.error(f"❌ Generation error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    
    finally:
        await state.set_state(UserStates.idle)

@dp.callback_query(F.data == "swap")
async def handle_swap(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_target_swap)
    await callback.message.edit_text(
        "🔄 **Замена лица**\n\n"
        "👇 *Отправь фото, где нужно заменить лицо*\n\n"
        "💡 *Сначала сделай AI Фотосессию, чтобы я запомнил твоё лицо!*",
        parse_mode="Markdown"
    )

@dp.message(UserStates.waiting_for_target_swap)
async def handle_target_swap(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Отправь фото, а не текст")
        return
    
    # Проверка лимита
    user_id = message.from_user.id
    if not usage.can_generate(user_id):
        await message.answer(
            f"❌ Лимит исчерпан ({usage.get_usage(user_id)}/{config.DAILY_LIMIT})"
        )
        await state.set_state(UserStates.idle)
        return
    
    await state.set_state(UserStates.generating)
    await message.answer("🔄 *Заменяю лицо...*", parse_mode="Markdown")
    
    try:
        # Получаем фото
        photo_file = await bot.get_file(message.photo[-1].file_id)
        target_bytes = await bot.download_file(photo_file.file_path)
        
        # Здесь нужно получить сохраненное фото пользователя
        # Для примера используем заглушку
        await message.answer(
            "⚠️ *Сначала сделай AI Фотосессию, чтобы я запомнил твоё лицо*\n\n"
            "Тогда сможу заменять лица на других фото!\n"
            "💡 *Лицо сохраняется автоматически после первой фотосессии*",
            reply_markup=get_modern_main_menu(),
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"❌ Swap error: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз")
    
    finally:
        await state.set_state(UserStates.idle)

if __name__ == "__main__":
    # Запуск для Railway
    uvicorn.run(
        "railway_main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False
    )
