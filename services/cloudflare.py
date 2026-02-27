import httpx
import base64
import logging
from typing import Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)

def prepare_image_for_cloudflare(
    image_bytes: bytes,
    max_size: int = 1024,
    quality: int = 85,
    format: str = "JPEG"
) -> bytes:
    """
    Изменяет размер изображения (сохраняя пропорции) и сжимает его.
    Возвращает байты оптимизированного изображения в указанном формате.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Конвертируем в RGB, если есть альфа-канал (для JPEG)
        if format.upper() == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        # Изменяем размер, сохраняя пропорции
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Сохраняем с указанным качеством
        output = io.BytesIO()
        img.save(output, format=format, quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Ошибка подготовки изображения: {e}")
        # В случае ошибки возвращаем оригинал
        return image_bytes

# ------------------------------------------------------------
# Генерация изображения по тексту (text-to-image)
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
# Генерация изображения на основе фото (img2img) – с ресайзом и сжатием
# ------------------------------------------------------------
async def generate_photoshoot_with_cloudflare(
    prompt: str,
    source_image_bytes: bytes,
    strength: float = 0.5,
    guidance_scale: float = 7.5,
    num_steps: int = 20,
    negative_prompt: str = "bad quality, blurry, distorted, extra limbs",
    max_image_size: int = 1024,
    image_quality: int = 85
) -> Optional[bytes]:
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev")

    # Подготавливаем изображение: ресайз + сжатие
    prepared_bytes = prepare_image_for_cloudflare(
        source_image_bytes,
        max_size=max_image_size,
        quality=image_quality,
        format="JPEG"  # можно "PNG", но JPEG даёт меньший размер
    )
    
    # Кодируем в base64
    image_b64 = base64.b64encode(prepared_bytes).decode('utf-8')
    
    # Формируем payload (Worker сам переименует поля при необходимости)
    payload = {
        "prompt": prompt,
        "image_b64": image_b64,
        "strength": strength,
        "guidance_scale": guidance_scale,
        "num_steps": num_steps,
        "negative_prompt": negative_prompt
        # width/height не передаём – они не нужны для img2img
    }
    headers = {"Content-Type": "application/json"}

    logger.info(f"📸 img2img: {prompt[:50]}..., strength={strength}, image size after prep: {len(prepared_bytes)} bytes")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ img2img error: {e}")
            return None
