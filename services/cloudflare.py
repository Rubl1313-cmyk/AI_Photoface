import httpx
import logging
from config import CF_WORKER_URL, CF_API_KEY

logger = logging.getLogger(__name__)

async def generate_with_cloudflare(prompt: str, style: str = "realistic", width: int = 1024, height: int = 1024, steps: int = 4) -> bytes:
    """
    Отправляет запрос на Cloudflare Workers AI и возвращает байты изображения.
    Предполагается, что Worker принимает JSON с полями prompt, style, width, height, steps.
    """
    if not CF_WORKER_URL:
        raise ValueError("CF_WORKER_URL не задан")
    if not CF_API_KEY:
        raise ValueError("CF_API_KEY не задан")

    headers = {
        "Authorization": f"Bearer {CF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt,
        "style": style,
        "width": width,
        "height": height,
        "steps": steps
    }
    logger.info(f"📡 Отправка запроса в Cloudflare: {prompt[:50]}...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(CF_WORKER_URL, json=payload, headers=headers)
        resp.raise_for_status()
        # Предполагаем, что Worker возвращает изображение в теле ответа (bytes)
        return resp.content
