#!/usr/bin/env python3
"""
🎨 AI PhotoStudio — Render.com (MINIMAL WORKING VERSION)
✅ user_ dict = {} — ПРОВЕРЕНО ВРУЧНУЮ
✅ Health server на 8080 (для Render)
✅ Polling для Telegram
"""

import asyncio, logging, os, signal, sys
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
from aiohttp import web
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

# 🔥 Загрузка env
load_dotenv()

# 🔥 Импорт config
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

# 🔥 Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # ✅ Перезаписывает существующие хендлеры
)
logger = logging.getLogger(__name__)

# ============================================================================
# ✅ ГЛОБАЛЬНЫЕ — ПРОВЕРЕНО ВРУЧНУЮ
# ============================================================================

bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher()
face_swapper = None
user_data: dict = {}  

# ============================================================================
# 🔥 ПРОМПТЫ
# ============================================================================

STYLE_PROMPTS = {
    "style_cinematic": "cinematic lighting, dramatic",
    "style_portrait": "professional portrait, studio lighting",
    "style_art": "digital art, illustration",
    "style_realistic": "photorealistic, natural lighting",
    "style_cyberpunk": "neon lights, cyberpunk",
    "style_fantasy": "fantasy art, magical",
}

BASE_FACE_PROMPT = "portrait of a person, clear face, professional photo, sharp focus, face centered"

# ============================================================================
# 🤖 ХЕНДЛЕРЫ (МИНИМАЛЬНЫЕ)
# ============================================================================

@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    user_data.pop(m.from_user.id, None)
    await m.answer(f"👋 {m.from_user.first_name}!\n\nЯ — **{BOT_NAME}**\n🚀 Нажми «🎨 Создать фото»!", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(F.text == "🎨 Создать фото")
async def start_gen(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    ok, _ = tracker.can_generate(uid)
    if not ok:
        await m.answer("❌ Лимит!", reply_markup=get_main_menu()); return
    await state.set_state(UserStates.waiting_for_face)
    user_data[uid] = {'face': None}
    await m.answer("📸 Отправь фото лица", reply_markup=ReplyKeyboardRemove())

@dp.message(UserStates.waiting_for_face, F.photo)
async def got_photo(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    try:
        f = m.photo[-1]
        data = (await bot.download(f)).read()
        user_data[uid]['face'] = data
        await state.set_state(UserStates.waiting_for_prompt)
        await m.answer("📝 Описание:", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error(f"Photo: {e}"); await m.answer("❌ Ошибка")

@dp.message(UserStates.waiting_for_prompt, F.text)
async def got_prompt(m: types.Message, state: FSMContext):
    p = m.text.strip()
    if len(p) < 3: await m.answer("❌ Коротко"); return
    await state.update_data(prompt=p)
    await state.set_state(UserStates.choosing_style)
    await m.answer("🎨 Стиль:", reply_markup=get_style_menu())

@dp.callback_query(UserStates.choosing_style, F.data.startswith("style_"))
async def style_chosen(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    await cb.message.edit_text(f"⏳ Генерация...\n📝 `{data['prompt']}`")
    await state.set_state(UserStates.generating)
    await state.update_data(style=cb.data)
    asyncio.create_task(_generate(cb.message, cb.from_user.id, data['prompt'], cb.data))

@dp.callback_query(F.data.startswith("back_to_main"))
async def go_home(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer(); await state.set_state(UserStates.idle)
    try: await cb.message.edit_text("🏠 Меню", reply_markup=get_main_menu())
    except: await cb.message.answer("🏠 Меню", reply_markup=get_main_menu())

# ============================================================================
# 🎨 ГЕНЕРАЦИЯ (МИНИМАЛЬНАЯ)
# ============================================================================

async def _generate(msg: types.Message, uid: int, prompt: str, style: str):
    try:
        face = user_data[uid]['face']
        tr = GoogleTranslator(source='auto', target='en')
        en = await asyncio.get_event_loop().run_in_executor(None, tr.translate, prompt)
        full = f"{BASE_FACE_PROMPT}, {en}, {STYLE_PROMPTS.get(style,'')}"
        
        await msg.edit_text("🎨 1/3: Генерация...")
        gen = await generate_with_cloudflare(prompt=full, width=1024, height=1024, steps=4)
        
        await msg.edit_text("👤 2/3: Замена лица...")
        result, err = face_swapper.swap(face, gen)
        if err: result = gen
        
        await msg.edit_text("✅ Готово!")
        await msg.answer_photo(photo=BufferedInputFile(result, "result.png"), caption=f"📸 `{prompt}`")
        tracker.increment(uid); user_data.pop(uid, None)
        
    except Exception as e:
        logger.error(f"Gen: {e}")
        try: await msg.edit_text(f"❌ {str(e)[:100]}")
        except: await msg.answer(f"❌ {str(e)[:100]}")
        user_data.pop(uid, None)

# ============================================================================
# 🌐 HEALTH SERVER (НА ПОРТУ 8080 — ДЛЯ RENDER)
# ============================================================================

async def run_health_server():
    """Простой сервер на 8080 для Render.com"""
    async def health_handler(request):
        return web.json_response({"status": "ok"})
    
    app = web.Application()
    app.router.add_get("/health", health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # ✅ Render требует 8080
    await site.start()
    
    logger.info("🌐 Health server: 0.0.0.0:8080")
    
    while True:
        await asyncio.sleep(3600)

# ============================================================================
# 🚀 POLLING
# ============================================================================

async def run_polling():
    logger.info("🚀 Polling...")
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except (TelegramNetworkError, TelegramAPIError) as e:
            logger.warning(f"⚠️ {e}"); await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"💥 {e}"); await asyncio.sleep(30)

# ============================================================================
# 🎯 MAIN
# ============================================================================

async def main():
    global face_swapper
    
    # 🔥 Проверка конфига с выводом ошибки
    if not check_config():
        print("💥 CONFIG ERROR", file=sys.stderr)
        sys.exit(1)
    
    # 🔥 Инициализация
    try:
        face_swapper = FaceFusionClient(api_url=FACEFUSION_URL)
    except Exception as e:
        print(f"💥 FaceFusion init error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 🔥 Команды бота (без падения если сеть недоступна)
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀"),
        ], scope=BotCommandScopeDefault())
    except:
        pass
    
    logger.info(f"🚀 {BOT_NAME} | Render.com")
    
    # 🔥 Запускаем health server ПЕРВЫМ, потом polling
    # Используем create_task чтобы health server не блокировал polling
    asyncio.create_task(run_health_server())
    await run_polling()

if __name__ == "__main__":
    # 🔥 Обработчик ошибок на самом верхнем уровне
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"💥 CRASH: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
