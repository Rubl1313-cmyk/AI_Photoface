# services/cloudflare.py
import httpx
import base64
import logging
import asyncio
import json
from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFilter
import io

logger = logging.getLogger(__name__)

# 🔑 Константы
MAX_IMAGE_KB = 400
MAX_DIMENSION = 512
JPEG_QUALITY = 90

# 🔑 Hugging Face API (InsightFace для детекции лица)
HF_API_URL = "https://api-inference.huggingface.co/models/dubzzz/insightface-face-detection"
HF_TOKEN = ""  # ← Добавьте в переменные окружения Render: HF_TOKEN=hf_xxx


def _compress_image(
    image_bytes: bytes,
    max_dimension: int = MAX_DIMENSION,
    max_kb: int = MAX_IMAGE_KB,
    quality: int = JPEG_QUALITY
) -> bytes:
    """Сжимает изображение для отправки в Cloudflare"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Ресайз
        w, h = img.size
        if w > max_dimension or h > max_dimension:
            ratio = min(max_dimension / w, max_dimension / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        
        # Сжатие JPEG
        output = io.BytesIO()
        for q in range(quality, 70, -5):
            output.seek(0)
            output.truncate(0)
            img.save(output, format="JPEG", quality=q, optimize=True)
            if len(output.getvalue()) / 1024 <= max_kb:
                logger.info(f"🗜️ Compressed: {len(output.getvalue())/1024:.1f}KB @ Q{q}")
                return output.getvalue()
        
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Compression error: {e}")
        return image_bytes


async def detect_face_hf(image_bytes: bytes) -> Optional[Dict[str, int]]:
    """
    Детекция лица через Hugging Face Inference API
    Возвращает bbox: {x, y, width, height} или None
    """
    global HF_TOKEN
    if not HF_TOKEN:
        import os
        HF_TOKEN = os.getenv("HF_TOKEN", "")
    
    if not HF_TOKEN:
        logger.warning("⚠️ HF_TOKEN not set")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            # Модель может быть в режиме loading — retry
            for attempt in range(3):
                resp = await client.post(
                    HF_API_URL,
                    headers={"Authorization": f"Bearer {HF_TOKEN}"},
                    content=image_bytes
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    if isinstance(result, list) and result and "box" in result[0]:
                        x1, y1, x2, y2 = result[0]["box"]
                        return {"x": int(x1), "y": int(y1), "width": int(x2-x1), "height": int(y2-y1)}
                    break
                elif resp.status_code == 503:
                    # Модель загружается
                    await asyncio.sleep(5)
                    continue
                else:
                    logger.error(f"❌ HF API {resp.status_code}: {resp.text[:150]}")
                    break
    except Exception as e:
        logger.error(f"❌ Face detection error: {e}")
    
    return None


def create_inpainting_mask(
    image_bytes: bytes,
    bbox: Optional[Dict[str, int]],
    padding: int = 40,
    blur: int = 12
) -> bytes:
    """
    Создаёт маску для inpainting:
    ⚫ Чёрный (0) = сохранить (лицо)
    ⚪ Белый (255) = изменить (фон)
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        # Белая маска по умолчанию (всё менять)
        mask = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(mask)
        
        if bbox:
            # Рисуем чёрный овал на месте лица
            cx = bbox["x"] + bbox["width"] // 2
            cy = bbox["y"] + bbox["height"] // 2
            rw = bbox["width"] // 2 + padding
            rh = bbox["height"] // 2 + padding
            draw.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=0)
        else:
            # Fallback: эвристика (верхняя центральная часть)
            fw, fh = int(w * 0.65), int(h * 0.6)
            fx, fy = (w - fw) // 2, int(h * 0.12)
            draw.ellipse([fx-padding, fy-padding, fx+fw+padding, fy+fh+padding], fill=0)
        
        # Размытие краёв для плавного перехода
        if blur > 0:
            mask = mask.filter(Image.GaussianBlur(radius=blur))
        
        # PNG без сжатия для маски
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        logger.error(f"❌ Mask creation error: {e}")
        # Fallback: белая маска
        fallback = Image.new("L", (512, 512), 255)
        fb_out = io.BytesIO()
        fallback.save(fb_out, format="PNG")
        return fb_out.getvalue()


def _no_none(data: Dict[str, Any]) -> Dict[str, Any]:
    """✅ ИСПРАВЛЕНО: Удаляет None значения из dict"""
    return {k: v for k, v in data.items() if v is not None}


# =============================================================================
# TEXT-TO-IMAGE (FLUX) — НЕ ТРОГАЕМ, работает как было
# =============================================================================
async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Text-to-Image через FLUX — без изменений"""
    import os
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = _no_none({
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "steps": 4,
        "negative_prompt": negative_prompt.strip() if negative_prompt else None,
    })
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"❌ FLUX error: {e}")
            return None


# =============================================================================
# 🎨 INPAINTING ДЛЯ «ИИ ФОТОСЕССИИ» — НОВАЯ ФУНКЦИЯ
# =============================================================================
async def generate_inpainting_photoshoot(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.9,
    guidance: float = 9.5,
    steps: int = 25,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    🎭 Inpainting для фотосессии:
    1. Детектируем лицо через HF API
    2. Создаём маску (лицо=чёрное, фон=белое)
    3. Отправляем в Cloudflare inpainting модель
    4. Возвращаем результат
    """
    import os
    
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # 1. Сжимаем исходное изображение
    compressed = _compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # 2. 🔑 Детекция лица через HF API
    logger.info("🔍 Detecting face via Hugging Face...")
    bbox = await detect_face_hf(compressed)
    
    if bbox:
        logger.info(f"✅ Face found: {bbox}")
    else:
        logger.warning("⚠️ Face not detected, using fallback mask")
    
    # 3. Создаём маску
    mask_bytes = create_inpainting_mask(compressed, bbox)
    mask_b64 = base64.b64encode(mask_bytes).decode()
    logger.info(f"🎭 Mask: {len(mask_bytes)} bytes")
    
    # 4. Формируем payload для Cloudflare
    payload = _no_none({
        "prompt": prompt.strip(),
        "image_b64": image_b64,
        "mask_b64": mask_b64,  # ← 🔑 КЛЮЧЕВОЕ: маска для inpainting
        "width": width,
        "height": height,
        "strength": strength,
        "guidance_scale": guidance,
        "num_steps": steps,
        "negative_prompt": negative_prompt.strip() if negative_prompt else None,
    })
    
    logger.info(f"🚀 Inpainting request: {len(json.dumps(payload))/1024:.1f}KB payload")
    
    # 5. Отправляем в Cloudflare
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            logger.info(f"✅ Inpainting success: {len(resp.content)} bytes")
            return resp.content
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ Inpainting error: {type(e).__name__}: {e}")
            return None
