import httpx
import logging
from deep_translator import GoogleTranslator
from config import CF_WORKER_URL, CF_API_KEY

logger = logging.getLogger(__name__)

# Инициализируем переводчик один раз
_translator = GoogleTranslator(source='ru', target='en')

# Бустеры для каждого стиля (повышают качество и соответствие стилю)
REALISM_BOOSTERS = {
    "realistic": "photorealistic, highly detailed, 8k, sharp focus, professional photo, natural lighting, depth of field, intricate details, ultra high quality",
    "anime": "anime style, cel shaded, vibrant colors, clean lines, Japanese animation style",
    "oil": "oil painting, impasto, textured brushstrokes, classic art, gallery quality",
    "sketch": "pencil sketch, hand-drawn, artistic, monochrome, detailed shading",
    "cyberpunk": "cyberpunk style, neon lights, dark cityscape, futuristic, sci-fi",
    "baroque": "baroque style, dramatic lighting, rich colors, classical art, ornate",
    "surreal": "surrealism, dreamlike, impossible scenes, Salvador Dali style",
    "comic": "comic book style, bold outlines, halftone dots, vibrant, sequential art",
    "photoreal": "photorealistic, ultra realistic, 4k, detailed, sharp, professional photography",
    "watercolor": "watercolor painting, soft edges, translucent colors, artistic",
    "pastel": "pastel colors, soft, gentle, chalk drawing, artistic",
    "3d": "3D render, octane render, cinematic lighting, highly detailed, CGI"
}

async def generate_with_cloudflare(prompt: str, style: str = "realistic", width: int = 1024, height: int = 1024, steps: int = 4) -> bytes:
    """
    Отправляет запрос на Cloudflare Workers AI и возвращает байты изображения.
    Предварительно переводит промпт с русского на английский и добавляет бустер для стиля.
    """
    if not CF_WORKER_URL:
        raise ValueError("CF_WORKER_URL не задан")
    if not CF_API_KEY:
        raise ValueError("CF_API_KEY не задан")

    # Добавляем бустер для выбранного стиля
    booster = REALISM_BOOSTERS.get(style, "")
    if booster:
        enhanced_prompt = f"{prompt}, {booster}"
    else:
        enhanced_prompt = prompt

    # Переводим промпт
    try:
        translated_prompt = _translator.translate(enhanced_prompt)
        logger.info(f"🔄 Перевод: '{enhanced_prompt[:50]}...' -> '{translated_prompt[:50]}...'")
    except Exception as e:
        logger.warning(f"Не удалось перевести промпт: {e}. Отправляем оригинал.")
        translated_prompt = enhanced_prompt

    headers = {
        "Authorization": f"Bearer {CF_API_KEY}",
    }

    # Формируем form-data (Worker ожидает именно такой формат)
    form_data = {
        "prompt": translated_prompt,
        "width": str(width),
        "height": str(height),
        "steps": str(steps)
    }

    logger.info(f"📡 Отправка запроса в Cloudflare с промптом: {translated_prompt[:50]}...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(CF_WORKER_URL, data=form_data, headers=headers)
        resp.raise_for_status()
        # Worker возвращает бинарные данные изображения
        return resp.content
