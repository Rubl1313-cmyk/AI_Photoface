import httpx
import logging
from deep_translator import GoogleTranslator
from config import CF_WORKER_URL, CF_API_KEY

logger = logging.getLogger(__name__)

# Инициализируем переводчик один раз для эффективности
_translator = GoogleTranslator(source='ru', target='en')

async def generate_with_cloudflare(prompt: str, style: str = "realistic", width: int = 1024, height: int = 1024, steps: int = 4) -> bytes:
    """
    Отправляет запрос на Cloudflare Workers AI и возвращает байты изображения.
    Предварительно переводит промпт с русского на английский.
    """
    if not CF_WORKER_URL:
        raise ValueError("CF_WORKER_URL не задан")
    if not CF_API_KEY:
        raise ValueError("CF_API_KEY не задан")

    # Переводим промпт
    try:
        translated_prompt = _translator.translate(prompt)
        logger.info(f"🔄 Перевод: '{prompt[:50]}...' -> '{translated_prompt[:50]}...'")
    except Exception as e:
        logger.warning(f"Не удалось перевести промпт: {e}. Отправляем оригинал.")
        translated_prompt = prompt

    headers = {
        "Authorization": f"Bearer {CF_API_KEY}",
        "Content-Type": "application/json"
    }

    # Отправляем как JSON, так как ваш Cloudflare Worker настроен на form-data?
    # Сейчас будем отправлять form-data, чтобы соответствовать коду Worker
    # Если Worker ожидает JSON, замените data=form_data на json=payload
    form_data = {
        "prompt": translated_prompt,
        "width": str(width),
        "height": str(height),
        "steps": str(steps)
    }
    # Если нужно передавать стиль, раскомментируйте:
    # form_data["style"] = style

    logger.info(f"📡 Отправка запроса в Cloudflare с переведённым промптом: {translated_prompt[:50]}...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(CF_WORKER_URL, data=form_data, headers=headers)
        resp.raise_for_status()
        # Предполагаем, что Worker возвращает изображение в теле ответа (bytes)
        return resp.content
