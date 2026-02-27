import httpx
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Существующая функция для text-to-image (FLUX)
async def generate_with_cloudflare(
    prompt: str,
    style: str = None,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Генерирует изображение по текстовому промпту через Cloudflare Workers (FLUX).
    """
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")
    
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": 4,  # можно сделать параметром, но пока фиксировано
        "negative_prompt": negative_prompt
    }
    
    headers = {"Content-Type": "application/json"}
    # Если нужен ключ: "Authorization": f"Bearer {os.getenv('CF_API_KEY')}"
    
    logger.info(f"📡 Отправка запроса в Cloudflare с промптом: {prompt[:50]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"Ошибка при генерации: {e}")
            return None

# НОВАЯ функция для img2img (фотосессия)
async def generate_photoshoot_with_cloudflare(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 1024,
    height: int = 1024,
    strength: float = 0.8,
    guidance: float = 7.5,
    num_steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Генерирует изображение на основе исходного фото (img2img) через Cloudflare Workers.
    Использует модель stable-diffusion-v1-5-img2img.
    """
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")
    
    # Кодируем исходное изображение в base64
    image_b64 = base64.b64encode(source_image_bytes).decode('utf-8')
    
    payload = {
        "prompt": prompt,
        "image_b64": image_b64,
        "width": width,
        "height": height,
        "strength": strength,
        "guidance": guidance,
        "num_steps": num_steps,
        "negative_prompt": negative_prompt,
        # Можно явно указать модель, если нужно:
        # "model": "@cf/runwayml/stable-diffusion-v1-5-img2img"
    }
    
    headers = {"Content-Type": "application/json"}
    
    logger.info(f"📸 Запрос на фотосессию: промпт '{prompt[:50]}...', strength={strength}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"Ошибка при генерации фотосессии: {e}")
            return None
