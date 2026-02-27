# services/cloudflare.py
import httpx
import base64
import logging
from typing import Optional, Dict, Any
from PIL import Image
import io

logger = logging.getLogger(__name__)

# 🔑 Константы: безопасные лимиты для Cloudflare Workers AI
MAX_IMAGE_RAW_KB = 400          # Макс. размер изображения до base64
MAX_IMAGE_DIMENSION = 512       # Макс. разрешение (ширина/высота)
JPEG_QUALITY = 85               # Стартовое качество JPEG
MIN_JPEG_QUALITY = 60           # Минимальное качество при сжатии


def prepare_image_for_cloudflare(
    image_bytes: bytes,
    max_dimension: int = MAX_IMAGE_DIMENSION,
    max_file_size_kb: int = MAX_IMAGE_RAW_KB,
    quality: int = JPEG_QUALITY,
    format: str = "JPEG"
) -> bytes:
    """
    Подготовка изображения для Cloudflare AI API:
    - Конвертирует в RGB
    - Ресайзит с сохранением пропорций
    - Итеративно сжимает до целевого размера
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Конвертация в RGB для JPEG
        if format.upper() == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        # Ресайз с сохранением пропорций
        original_w, original_h = img.size
        if original_w > max_dimension or original_h > max_dimension:
            ratio = min(max_dimension / original_w, max_dimension / original_h)
            new_size = (int(original_w * ratio), int(original_h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"📐 Resized: {original_w}x{original_h} → {new_size[0]}x{new_size[1]}")
        
        # Итеративное сжатие до целевого размера
        output = io.BytesIO()
        current_quality = quality
        
        while current_quality >= MIN_JPEG_QUALITY:
            output.seek(0)
            output.truncate(0)
            img.save(output, format=format, quality=current_quality, optimize=True)
            
            size_kb = len(output.getvalue()) / 1024
            if size_kb <= max_file_size_kb:
                logger.info(f"🗜️ Compressed: {size_kb:.1f} KB @ quality={current_quality}")
                return output.getvalue()
            current_quality -= 5
        
        # Если не удалось сжать до лимита — возвращаем лучшее, что есть
        final_size_kb = len(output.getvalue()) / 1024
        logger.warning(f"⚠️ Could not compress to {max_file_size_kb}KB, sending {final_size_kb:.1f}KB")
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"❌ Image preparation error: {e}")
        return image_bytes  # Fallback: возвращаем оригинал


def _filter_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет ключи со значением None из словаря"""
    return {k: v for k, v in data.items() if v is not None}


async def generate_with_cloudflare(
    prompt: str,
    style: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Text-to-Image генерация через FLUX.1 Schnell"""
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

    payload = _filter_none_values({
        "prompt": prompt.strip(),
        "width": int(width),
        "height": int(height),
        "steps": 4,
        "negative_prompt": negative_prompt.strip() if negative_prompt else None,
    })

    logger.info(f"📡 text-to-image: {prompt[:50]}... | {width}x{height}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ text-to-image error: {type(e).__name__}: {e}")
            return None


async def generate_photoshoot_with_cloudflare(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.5,
    guidance_scale: float = 7.5,
    num_steps: int = 20,
    negative_prompt: str = "bad quality, blurry, distorted, extra limbs",
    max_image_size: int = MAX_IMAGE_DIMENSION,
    image_quality: int = JPEG_QUALITY
) -> Optional[bytes]:
    """Img2Img генерация через Stable Diffusion v1.5"""
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

    # 1. Подготовка изображения
    prepared_bytes = prepare_image_for_cloudflare(
        source_image_bytes,
        max_dimension=max_image_size,
        max_file_size_kb=MAX_IMAGE_RAW_KB,
        quality=image_quality,
        format="JPEG"
    )
    
    # 2. Кодирование в base64
    image_b64 = base64.b64encode(prepared_bytes).decode("utf-8")
    
    # 3. Логирование размеров
    raw_kb = len(prepared_bytes) / 1024
    b64_kb = len(image_b64) / 1024
    logger.info(f"🖼️ Prepared: {raw_kb:.1f}KB raw → {b64_kb:.1f}KB base64")
    
    # 4. Формирование payload (только non-None значения)
    payload = _filter_none_values({
        "prompt": prompt.strip(),
        "image_b64": image_b64,
        "width": int(width) if width else None,
        "height": int(height) if height else None,
        "strength": float(strength) if strength is not None else None,
        "guidance_scale": float(guidance_scale) if guidance_scale is not None else None,
        "num_steps": int(num_steps) if num_steps else None,
        "negative_prompt": negative_prompt.strip() if negative_prompt else None,
    })
    
    logger.info(f"📸 img2img: {prompt[:50]}... | strength={strength} | steps={num_steps}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ img2img error: {type(e).__name__}: {e}")
            return None
