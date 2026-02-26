#!/usr/bin/env python3
"""🎨 AI PhotoStudio — Render.com (Webhook, working)"""

import asyncio, logging, os, signal, sys
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()
from config import TG_BOT_TOKEN, CF_WORKER_URL, CF_API_KEY, BOT_NAME, DAILY_LIMIT, FACEFUSION_URL, WEBHOOK_PATH, check_config
from states import UserStates
from keyboards import get_main_menu, get_style_menu
from services.cloudflare import generate_with_cloudflare
from services.face_fusion_api import FaceFusionClient
from services.usage import tracker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', handlers=[logging.StreamHandler(sys.stdout)], force=True)
logger = logging.getLogger(__name__)

# ✅ ГЛОБАЛЬНЫЕ
bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher()
face_swapper = None
user_data: dict = {}  

# 🔥 ПРОМПТЫ — ИСПРАВЛЕНО: пользовательский промпт ГЛАВНЫЙ
STYLE_PROMPTS = {
    "style_cinematic": "cinematic lighting, dramatic, film grain, movie scene",
    "style_portrait": "professional portrait, studio lighting",
    "style_art": "digital art, illustration, artistic",
    "style_realistic": "photorealistic, natural lighting, sharp focus",
    "style_cyberpunk": "neon lights, cyberpunk, futuristic, sci-fi",
    "style_fantasy": "fantasy art, magical, ethereal",
}

# 🔥 ИСПРАВЛЕНО: МЕНЬШЕ ограничений, больше свободы для сцен
BASE_FACE_PROMPT = "high quality, detailed, professional"

# 🔥 Словарь гендеров
GENDER_KEYWORDS = {
    'мужчина': 'man, male, masculine',
    'мужской': 'man, male',
    'парень': 'young man, male',
    'женщина': 'woman, female, feminine',
    'женский': 'woman, female',
    'девушка': 'young woman, female',
}

def enhance_prompt(user_prompt: str, translated: str) -> str:
    """Добавляет гендер если указан"""
    prompt_lower = user_prompt.lower()
    for ru, en in GENDER_KEYWORDS.items():
        if ru in prompt_lower:
            return f"{en}, {translated}"
    return translated

# 🤖 ХЕНДЛЕРЫ (без изменений)
@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear(); user_data.pop(m.from_user.id, None)
    await m.answer(f"👋 {m.from_user.first_name}!\n\nЯ — **{BOT_NAME}**\n🚀 Нажми «🎨 Создать фото»!", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(F.text == "🎨 Создать фото")
async def start_gen(m: types.Message, state: FSMContext):
    uid = m.from_user.id; ok, _ = tracker.can_generate(uid)
    if not ok: await m.answer("❌ Лимит!", reply_markup=get_main_menu()); return
    await state.set_state(UserStates.waiting_for_face); user_data[uid] = {'face': None}
    await m.answer("📸 Отправь фото лица", reply_markup=ReplyKeyboardRemove())

@dp.message(UserStates.waiting_for_face, F.photo | F.document)
async def got_photo(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    try:
        f = m.photo[-1] if m.photo else m.document
        if not f: await m.answer("❌ Нет файла"); return
        data = (await bot.download(f)).read()
        if len(data) > 10_000_000: await m.answer("❌ >10MB"); return
        user_data[uid]['face'] = data
        await state.set_state(UserStates.waiting_for_prompt)
        await m.answer("📝 Описание (пиши что хочешь!):\n💡 `мужчина на коне, вестерн`", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    except Exception as e: logger.error(f"Photo: {e}"); await m.answer("❌ Ошибка")

@dp.message(UserStates.waiting_for_prompt, F.text)
async def got_prompt(m: types.Message, state: FSMContext):
    p = m.text.strip()
    if len(p) < 3: await m.answer("❌ Коротко"); return
    await state.update_data(prompt=p); await state.set_state(UserStates.choosing_style)
    await m.answer("🎨 Стиль:", reply_markup=get_style_menu())

@dp.callback_query(UserStates.choosing_style, F.data.startswith("style_"))
async def style_chosen(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer(); data = await state.get_data()
    await cb.message.edit_text(f"⏳ Генерация...\n📝 `{data['prompt']}`")
    await state.set_state(UserStates.generating); await state.update_data(style=cb.data)
    asyncio.create_task(_generate(cb.message, cb.from_user.id, data['prompt'], cb.data))

@dp.callback_query(F.data.startswith("back_to_main"))
async def go_home(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer(); await state.set_state(UserStates.idle)
    try: await cb.message.edit_text("🏠 Меню", reply_markup=get_main_menu())
    except: await cb.message.answer("🏠 Меню", reply_markup=get_main_menu())

# 🎨 ГЕНЕРАЦИЯ — ИСПРАВЛЕНО: ПОЛЬЗОВАТЕЛЬСКИЙ ПРОМПТ ГЛАВНЫЙ
async def _generate(msg: types.Message, uid: int, prompt: str, style: str):
    try:
        face = user_data[uid]['face']
        
        # 🔤 Перевод
        tr = GoogleTranslator(source='auto', target='en')
        en = await asyncio.get_event_loop().run_in_executor(None, tr.translate, prompt)
        
        # 🔥 Добавляем гендер если указан
        en_with_gender = enhance_prompt(prompt, en)
        
        # 🔥 ФОРМИРУЕМ ПРОМПТ: пользовательский ГЛАВНЫЙ, BASE минимальный
        style_text = STYLE_PROMPTS.get(style, "")
        
        # ✅ ИСПРАВЛЕНО: порядок ВАЖЕН — пользовательский промпт ПЕРВЫЙ
        full_prompt = f"{en_with_gender}, {style_text}, {BASE_FACE_PROMPT}".strip()
        
        logger.info(f"🔤 Перевод: '{prompt}' → '{en_with_gender}'")
        logger.info(f"🎨 Промпт: {full_prompt}")
        
        # 🎨 Генерация
        await msg.edit_text("🎨 1/3...")
        gen = await generate_with_cloudflare(prompt=full_prompt, width=1024, height=1024, steps=4)
        
        # 👤 Замена лица
        await msg.edit_text("👤 2/3...")
        result, err = face_swapper.swap(face, gen)
        if err: result = gen
        
        # ✅ Результат
        await msg.edit_text("✅ Готово!")
        await msg.answer_photo(photo=BufferedInputFile(result, "result.png"), caption=f"📸 `{prompt}`")
        tracker.increment(uid); user_data.pop(uid, None)
        
    except Exception as e:
        logger.error(f"Gen: {e}")
        try: await msg.edit_text(f"❌ {str(e)[:100]}")
        except: await msg.answer(f"❌ {str(e)[:100]}")
        user_data.pop(uid, None)

# 🌐 WEBHOOK (без изменений)
async def run_webhook():
    logger.info("🚀 Webhook...")
    app = web.Application()
    async def health_handler(request): return web.json_response({"status": "ok"})
    app.router.add_get("/health", health_handler)
    logger.info("✅ /health")
    wp = os.getenv("WEBHOOK_PATH", "/webhook")
    logger.info(f"🔗 Webhook: {wp}")
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=wp)
    logger.info("✅ Webhook handler")
    setup_application(app, dp, bot=bot)
    logger.info("✅ setup_application")
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080); await site.start()
    logger.info("🌐 Server: 0.0.0.0:8080")
    logger.info("✅ Bot ready!")
    while True: await asyncio.sleep(3600)

async def main():
    global face_swapper
    if not check_config(): sys.exit(1)
    face_swapper = FaceFusionClient(api_url=FACEFUSION_URL)
    try:
        await bot.delete_webhook()
        logger.info("✅ Webhook deleted")
    except Exception as e: logger.warning(f"⚠️ {e}")
    logger.info(f"🚀 {BOT_NAME} | Webhook (Render)")
    await run_webhook()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    try: asyncio.run(main())
    except Exception as e: print(f"💥 CRASH: {e}", file=sys.stderr); sys.exit(1)
