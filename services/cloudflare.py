import httpx
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Генерация изображения по тексту (text-to-image)
# Использует модель FLUX (или другую)
# ------------------------------------------------------------
async def generate_with_cloudflare(
    prompt: str,
    style: str = None,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": 4,
        "negative_prompt": negative_prompt
    }
    headers = {"Content-Type": "application/json"}

    logger.info(f"📡 text-to-image: {prompt[:50]}...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ text-to-image error: {e}")
            return None


# ------------------------------------------------------------
# Генерация изображения на основе фото (img2img)
# Использует stable-diffusion-v1-5-img2img
# ------------------------------------------------------------
async def generate_photoshoot_with_cloudflare(
    prompt: str,
    source_image_bytes: bytes,
    strength: float = 0.8,
    guidance: float = 7.5,
    num_steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")

    # Кодируем изображение в base64
    image_b64 = base64.b64encode(source_image_bytes).decode('utf-8')

    # Только поля, поддерживаемые моделью img2img
    payload = {
        "prompt": prompt,
        "image_b64": image_b64,
        "strength": strength,
        "guidance": guidance,
        "num_steps": num_steps,
        "negative_prompt": negative_prompt
    }
    headers = {"Content-Type": "application/json"}

    logger.info(f"📸 img2img: {prompt[:50]}..., strength={strength}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ img2img error: {e}")
            return None
