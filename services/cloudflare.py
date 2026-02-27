import httpx
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Генерация изображения по текстовому промпту (text-to-image)
# Использует модель FLUX (или другую, заданную в Worker)
# ------------------------------------------------------------
async def generate_with_cloudflare(
    prompt: str,
    style: str = None,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Генерирует изображение по текстовому описанию через Cloudflare Workers.
    Возвращает байты PNG-изображения или None при ошибке.
    """
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")
    
    # Формируем запрос
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": 4,  # для FLUX оптимально 4
        "negative_prompt": negative_prompt
    }
    # Если нужно указать конкретную модель, можно добавить поле "model"
    # payload["model"] = "@cf/black-forest-labs/flux-1-schnell"
    
    headers = {"Content-Type": "application/json"}
    # Если требуется аутентификация
    # api_key = os.getenv("CF_API_KEY")
    # if api_key:
    #     headers["Authorization"] = f"Bearer {api_key}"

    logger.info(f"📡 Отправка запроса в Cloudflare (text-to-image): {prompt[:50]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации через Cloudflare: {e}")
            return None


# ------------------------------------------------------------
# Генерация изображения на основе исходного фото (img2img)
# Использует модель stable-diffusion-v1-5-img2img
# ------------------------------------------------------------
async def generate_photoshoot_with_cloudflare(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.8,
    guidance: float = 7.5,
    num_steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Генерирует новое изображение на основе загруженной фотографии (img2img).
    Возвращает байты PNG-изображения или None при ошибке.
    """
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")
    
    # Кодируем исходное изображение в base64
    image_b64 = base64.b64encode(source_image_bytes).decode('utf-8')
    
    # Подготавливаем payload. Worker сам сконвертирует base64 в нужный формат.
    payload = {
        "prompt": prompt,
        "image_b64": image_b64,
        "width": width,
        "height": height,
        "strength": strength,
        "guidance": guidance,
        "num_steps": num_steps,
        "negative_prompt": negative_prompt
    }
    # Можно явно указать модель img2img
    # payload["model"] = "@cf/runwayml/stable-diffusion-v1-5-img2img"
    
    headers = {"Content-Type": "application/json"}
    
    logger.info(f"📸 Запрос в Cloudflare (img2img): промпт '{prompt[:50]}...', размер {width}x{height}, strength={strength}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации фотосессии: {e}")
            return None
