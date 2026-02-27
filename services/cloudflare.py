import httpx
import base64
import logging
from typing import Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)

def convert_to_png(image_bytes: bytes) -> bytes:
    """Конвертирует изображение в формат PNG."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Конвертируем в RGB, если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()
    except Exception as e:
        logger.error(f"Ошибка конвертации в PNG: {e}")
        return image_bytes  # возвращаем оригинал, если не удалось

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

async def generate_photoshoot_with_cloudflare(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.8,
    guidance_scale: float = 7.5,      # обратите внимание: guidance_scale, не guidance
    num_steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")

    # Конвертируем в PNG (Pillow)
    png_bytes = convert_to_png(source_image_bytes)
    image_b64 = base64.b64encode(png_bytes).decode('utf-8')

    payload = {
        "prompt": prompt,
        "image_b64": image_b64,
        "width": width,
        "height": height,
        "strength": strength,
        "guidance_scale": guidance_scale,   # ← именно guidance_scale
        "num_steps": num_steps,
        "negative_prompt": negative_prompt
    }
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ img2img error: {e}")
            return None
