#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Telegram бот для Render.com
✅ user_ dict = {} (ПРАВИЛЬНЫЙ СИНТАКСИС)
✅ Гендер в промпте (мужчина/женщина)
✅ Отправка full_prompt в Cloudflare
"""

import asyncio, logging, os, signal, sys, time, re
from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, BotCommand, BotCommandScopeDefault,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()
from config import (
    TG_BOT_TOKEN, CF_WORKER_URL, CF_API_KEY,
    BOT_NAME, DAILY_LIMIT, PORT, FACEFUSION_URL,
    check_config
)
from states import UserStates
from keyboards import get_main_menu, get_style_menu, get_result_keyboard
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import tracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# ============================================================================
# ✅ ГЛОБАЛЬНЫЕ
# ============================================================================

bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher()
face_swapper = None
user_data: dict = {}  # ✅ ПРАВИЛЬНО

# ============================================================================
# 🔥 ПРОМПТЫ — С ГЕНДЕРОМ
# ============================================================================

STYLE_PROMPTS = {
    "style_cinematic": "cinematic lighting, dramatic, film grain",
    "style_portrait": "professional portrait, studio lighting, soft shadows",
    "style_art": "digital art, illustration, vibrant colors",
    "style_realistic": "photorealistic, natural lighting, sharp focus",
    "style_cyberpunk": "neon lights, cyberpunk, futuristic",
    "style_fantasy": "fantasy art, magical, ethereal lighting",
}

# 🔥 Без "looking at camera" — пользователь контролирует взгляд
BASE_FACE_PROMPT = (
    "portrait of a person, clear face, professional photo, "
    "sharp focus, face centered, high quality, detailed face, "
    "no hands in frame, no body parts visible, face only, "
    "headshot, upper body only, clean background, studio lighting"
)

# 🔥 Словарь гендеров для явного указания в промпте
GENDER_KEYWORDS = {
    'мужчина': 'man, male, masculine',
    'мужской': 'man, male, masculine',
    'парень': 'young man, male',
    'парень': 'young man, male',
    'женщина': 'woman, female, feminine',
    'женский': 'woman, female, feminine',
    'девушка': 'young woman, female',
    'девочка': 'girl, young female',
    'мальчик': 'boy, young male',
}

def enhance_prompt_with_gender(user_prompt: str, translated: str) -> str:
    """Добавляет явный гендер в промпт если пользователь указал"""
    prompt_lower = user_prompt.lower()
    for ru_keyword, en_gender in GENDER_KEYWORDS.items():
        if ru_keyword in prompt_lower:
            # Добавляем гендер в начало переведённого промпта
            return f"{en_gender}, {translated}"
    return translated

# ============================================================================
# 🤖 ХЕНДЛЕРЫ
# ============================================================================

@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    user_data.pop(m.from_user.id, None)
    await m.answer(f"👋 {m.from_user.first_name}!\n\nЯ — **{BOT_NAME}** 🎨\n• Генерация + замена лица\n• {DAILY_LIMIT}/день\n\n🚀 Нажми «🎨 Создать фото»!", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(m: types.Message):
    await m.answer(tracker.get_stats_text(m.from_user.id), parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    await m.answer(f"❓ **Помощь**\n\n1. 🎨 Создать фото\n2. Фото лица → описание → стиль\n3. Жди ~30-60 сек\n\n📊 Лимит: {DAILY_LIMIT}/день", parse_mode="Markdown")

@dp.message(F.text == "🎨 Создать фото")
async def start_gen(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    ok, _ = tracker.can_generate(uid)
    if not ok: await m.answer("❌ Лимит!", reply_markup=get_main_menu(), parse_mode="Markdown"); return
    await state.set_state(UserStates.waiting_for_face)
    user_data[uid] = {'face': None}
    await m.answer("📸 Отправь фото лица", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(UserStates.waiting_for_face, F.photo | F.document)
async def got_photo(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    try:
        f = m.photo[-1] if m.photo else m.document
        if m.document and not m.document.mime_type.startswith('image/'):
            await m.answer("❌ Не изображение", parse_mode="Markdown"); return
        data = (await bot.download(f)).read()
        if len(data) > 10_000_000:
            await m.answer("❌ >10MB", parse_mode="Markdown"); return
        user_data[uid]['face'] = data
        await state.set_state(UserStates.waiting_for_prompt)
        await m.answer("📝 Описание (пиши на русском!):\n💡 `мужчина в костюме, офис`", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Photo: {e}"); await m.answer("❌ Ошибка", parse_mode="Markdown")

@dp.message(UserStates.waiting_for_prompt, F.text)
async def got_prompt(m: types.Message, state: FSMContext):
    p = m.text.strip()
    if len(p) < 3 or len(p) > 200:
        await m.answer("❌ 3-200 символов", parse_mode="Markdown"); return
    await state.update_data(prompt=p)
    await state.set_state(UserStates.choosing_style)
    await m.answer("🎨 Стиль:", reply_markup=get_style_menu(), parse_mode="Markdown")

@dp.callback_query(UserStates.choosing_style, F.data.startswith("style_"))
async def style_chosen(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    await cb.message.edit_text(f"⏳ Генерация...\n📝 `{data['prompt']}`\n🎨 `{cb.data}`", parse_mode="Markdown")
    await state.set_state(UserStates.generating)
    await state.update_data(style=cb.data)
    asyncio.create_task(_generate(cb.message, cb.from_user.id, data['prompt'], cb.data))

@dp.callback_query(F.data == "style_skip")
async def style_skip(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer(); await style_chosen(cb, state)

@dp.callback_query(F.data.startswith("back_to_main"))
async def go_home(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer(); await state.set_state(UserStates.idle)
    try: await cb.message.edit_text("🏠 Меню", reply_markup=get_main_menu(), parse_mode="Markdown")
    except: await cb.message.answer("🏠 Меню", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("retry_"))
async def retry_gen(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    uid = cb.from_user.id; data = await state.get_data()
    if not data.get('prompt') or uid not in user_ await cb.message.answer("❌ Начни сначала", parse_mode="Markdown"); await go_home(cb, state); return
    await cb.message.edit_text("🔄 Повтор...", parse_mode="Markdown")
    asyncio.create_task(_generate(cb.message, uid, data['prompt'], data.get('style','style_realistic')))

# ============================================================================
# 🎨 ГЕНЕРАЦИЯ — С ГЕНДЕРОМ И ПЕРЕВОДОМ
# ============================================================================

async def _generate(msg: types.Message, uid: int, prompt: str, style: str):
    try:
        ok, _ = tracker.can_generate(uid)
        if not ok: await msg.edit_text("❌ Лимит!", parse_mode="Markdown"); return
        face = user_data[uid]['face']
        
        # 🔤 Перевод + усиление гендером
        tr = GoogleTranslator(source='auto', target='en')
        en = await asyncio.get_event_loop().run_in_executor(None, tr.translate, prompt)
        
        # 🔥 Добавляем явный гендер если пользователь указал
        en_with_gender = enhance_prompt_with_gender(prompt, en)
        logger.info(f"🔤 Перевод: '{prompt}' → '{en_with_gender}'")
        
        # 🔥 Формируем полный промпт
        style_text = STYLE_PROMPTS.get(style, "")
        full_prompt = f"{BASE_FACE_PROMPT}, {en_with_gender}, {style_text}".strip()
        logger.info(f"🎨 Промпт: {full_prompt[:150]}...")
        
        # 🎨 Шаг 1: Генерация
        await msg.edit_text("🎨 1/3: Генерация...", parse_mode="Markdown")
        gen = await generate_with_cloudflare(prompt=full_prompt, width=1024, height=1024, steps=4)
        if len(gen) < 1000: raise RuntimeError("Пустой ответ")
        
        # 👤 Шаг 2: Замена лица
        await msg.edit_text("👤 2/3: Замена лица...", parse_mode="Markdown")
        result, err = face_swapper.swap(face, gen)
        if err: logger.warning(f"⚠️ {err}"); result = gen
        
        # ✅ Шаг 3: Отправка
        await msg.edit_text("✅ 3/3: Готово!", parse_mode="Markdown")
        sn = style.replace("style_","") if style else "без стиля"
        await msg.answer_photo(photo=BufferedInputFile(result, "result.png"), caption=f"📸 Готово!\n📝 `{prompt}`\n🎨 `{sn}`", reply_markup=get_result_keyboard(f"g_{uid}_{int(time.time())}"), parse_mode="Markdown")
        tracker.increment(uid); user_data.pop(uid, None)
        try: await msg.delete()
        except: pass
        
    except TelegramAPIError as e:
        logger.error(f"TG: {e}")
        try: await msg.edit_text(f"❌ {str(e)[:100]}", parse_mode="Markdown")
        except: await msg.answer(f"❌ {str(e)[:100]}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Gen: {e}", exc_info=True)
        try: await msg.edit_text(f"❌ {str(e)[:150]}", parse_mode="Markdown")
        except: await msg.answer(f"❌ {str(e)[:150]}", parse_mode="Markdown")
        user_data.pop(uid, None)

# ============================================================================
# 🚀 POLLING
# ============================================================================

async def run_polling():
    logger.info("🚀 Polling режим...")
    while True:
        try:
            logger.info("🔄 Start polling...")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except (TelegramNetworkError, TelegramAPIError) as e:
            logger.warning(f"⚠️ Telegram ошибка: {e}")
            logger.info("🔄 Повтор через 30 секунд...")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"💥 Polling crash: {e}", exc_info=True)
            logger.info("🔄 Повтор через 30 секунд...")
            await asyncio.sleep(30)

async def main():
    global face_swapper
    if not check_config(): logger.error("💥 Config error"); sys.exit(1)
    face_swapper = FaceFusionClient(api_url=FACEFUSION_URL)
    try:
        await bot.set_my_commands([BotCommand(command="start", description="🚀"), BotCommand(command="stats", description="📊"), BotCommand(command="help", description="❓")], scope=BotCommandScopeDefault())
    except Exception as e: logger.warning(f"⚠️ Commands: {e}")
    logger.info(f"🚀 {BOT_NAME} | Polling режим (Render.com)")
    await run_polling()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("👋 Прервано")
    except Exception as e: logger.error(f"💥 Crash: {e}", exc_info=True); sys.exit(1)
