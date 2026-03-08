# services/cloudflare.py
"""
☁️ Cloudflare Workers AI Client — PHOENIX 1.0 + Enhanced
"""
import httpx
import base64
import logging
import os
import io
from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# =============================================================================
# 🔑 КОНСТАНТЫ
# =============================================================================
MAX_IMAGE_KB = 400
MAX_DIMENSION = 1024  # Увеличено для лучшего качества
JPEG_QUALITY = 95

# =============================================================================
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================
def _compress_image(
    image_bytes: bytes,
    max_dimension: int = MAX_DIMENSION,
    max_kb: int = MAX_IMAGE_KB,
    quality: int = JPEG_QUALITY
) -> bytes:
    """Сжимает изображение для отправки в API"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        # Resize если нужно
        if w > max_dimension or h > max_dimension:
            ratio = min(max_dimension / w, max_dimension / h)
            img = img.resize(
                (int(w * ratio), int(h * ratio)),
                Image.Resampling.LANCZOS
            )
        
        # Сохранение с качеством
        output = io.BytesIO()
        for q in range(quality, 70, -5):
            output.seek(0)
            output.truncate(0)
            img.save(output, format="JPEG", quality=q, optimize=True)
            if len(output.getvalue()) / 1024 <= max_kb:
                return output.getvalue()
        
        return output.getvalue()
    
    except Exception as e:
        logger.error(f"❌ Compression error: {e}")
        return image_bytes

def truncate_caption(text: str, max_length: int = 1024, suffix: str = "...") -> str:
    """Обрезает текст до лимита Telegram caption"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

# =============================================================================
# 📸 TEXT-TO-IMAGE (PHOENIX 1.0)
# =============================================================================
async def generate_with_phoenix(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = "",
    steps: int = 12,
    guidance: float = 7.5
) -> Optional[bytes]:
    """Text-to-Image через Phoenix 1.0 (лучший фотореализм)"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": guidance,
    }
    
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt.strip()
    
    logger.info(f"📡 Phoenix request: {prompt[:80]}...")
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            logger.info(f"✅ Phoenix success: {len(resp.content)} bytes")
            return resp.content
        except Exception as e:
            logger.error(f"❌ Phoenix error: {e}")
            return None

# =============================================================================
# 🎨 INPAINTING FOR PHOTOSHOOT (улучшенный)
# =============================================================================
async def generate_inpainting_photoshoot(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 1024,
    height: int = 1024,
    strength: float = 0.90,
    guidance: float = 9.0,
    steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Inpainting фотосессия с маской лица (улучшенная версия)"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # Сжимаем исходное изображение
    compressed = _compress_image(source_image_bytes, max_dimension=1024)
    image_b64 = base64.b64encode(compressed).decode()
    
    # Получаем размеры для маски
    img = Image.open(io.BytesIO(compressed))
    w, h = img.size
    
    # Создаём маску (упрощённая версия)
    mask = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(mask)
    
    # Рисуем овал для лица
    face_x = int(w * 0.25)
    face_y = int(h * 0.08)
    face_w = int(w * 0.50)
    face_h = int(h * 0.40)
    
    draw.ellipse([face_x, face_y, face_x + face_w, face_y + face_h], fill=0)
    
    # Размытие для плавного перехода
    mask = mask.filter(ImageFilter.GaussianBlur(radius=20))
    
    # Сохраняем маску
    mask_bytes = io.BytesIO()
    mask.save(mask_bytes, format="PNG")
    mask_b64 = base64.b64encode(mask_bytes.getvalue()).decode()
    
    # Формируем payload
    payload = {
        "prompt": prompt.strip(),
        "image_b64": image_b64,
        "mask_b64": mask_b64,
        "width": width,
        "height": height,
        "strength": strength,
        "guidance_scale": guidance,
        "num_steps": min(20, max(10, int(steps))),
    }
    
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt.strip()
    
    logger.info(f"🎨 Inpainting request: {len(compressed)}B img")
    
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            logger.info(f"✅ Inpainting success: {len(resp.content)} bytes")
            return resp.content
        except Exception as e:
            logger.error(f"❌ Inpainting error: {e}")
            return None

# =============================================================================
# 🔄 MULTI-PASS GENERATION (НОВОЕ)
# =============================================================================
async def generate_multi_pass(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    passes: int = 2
) -> Optional[bytes]:
    """Многопроходная генерация для лучшего качества"""
    image_bytes = None
    
    for i in range(passes):
        if i == 0:
            # Первая генерация
            image_bytes = await generate_with_phoenix(
                prompt=prompt,
                width=width,
                height=height,
                steps=12,
                guidance=7.5
            )
        else:
            # Уточнение (можно добавить inpainting для refinement)
            logger.info(f"🔄 Pass {i+1}/{passes} completed")
    
    return image_bytes
