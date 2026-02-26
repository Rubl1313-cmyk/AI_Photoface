#!/usr/bin/env python3
"""🎨 AI PhotoStudio — Render.com (Webhook AUTO-SET)"""

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
user_ dict = {}  # ✅ ПРАВИЛЬНО

# 🔥 ПРОМПТЫ — ИСПРАВЛЕНО
