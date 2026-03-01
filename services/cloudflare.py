# services/cloudflare.py
"""
☁️ Cloudflare Workers API Client — FINAL FIXED
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
MAX_DIMENSION = 512
JPEG_QUALITY = 90

FACE_DETECT_SPACE_URL = os.getenv(
    "FACE_DETECT_SPACE_URL",
    "https://dmitry1313-face-swaper.hf.space/detect"
)


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
        
        if w > max_dimension or h > max_dimension:
            ratio = min(max_dimension / w, max_dimension / h)
            img = img.resize(
                (int(w * ratio), int(h * ratio)),
                Image.Resampling.LANCZOS
            )
        
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
# 🔍 DETECT FACE VIA HF SPACE
# =============================================================================

async def detect_face_via_space(image_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Детекция лица через HF Space"""
    if not FACE_DETECT_SPACE_URL:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
            headers = {}
            secret = os.getenv("FACE_DETECT_SECRET")
            if secret:
                headers["Authorization"] = f"Bearer {secret}"
            
            response = await client.post(
                FACE_DETECT_SPACE_URL,
                files=files,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("face"):
                    face = result["face"]
                    img_size = result.get("image_size", {})
                    return {
                        "x": face["x"],
                        "y": face["y"],
                        "width": face["width"],
                        "height": face["height"],
                        "score": face["score"],
                        "image_width": img_size.get("width"),
                        "image_height": img_size.get("height")
                    }
    except Exception as e:
        logger.error(f"❌ Face detect error: {e}")
    
    return None


# =============================================================================
# 🎭 MASK CREATION FOR INPAINTING
# =============================================================================

def create_inpainting_mask(
    image_bytes: bytes,
    face_bbox: Optional[Dict[str, int]],
    width: int,
    height: int,
    face_padding_percent: float = 0.20,
    blur_radius: int = 15,
    use_oval_shape: bool = True
) -> bytes:
    """Создаёт маску для inpainting: чёрный=лицо(сохранить), белый=фон(менять)"""
    try:
        mask = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(mask)
        
        if face_bbox and face_bbox.get("width", 0) > 20:
            cx = face_bbox["x"] + face_bbox["width"] // 2
            cy = face_bbox["y"] + face_bbox["height"] // 2
            face_width = face_bbox["width"]
            face_height = face_bbox["height"]
            
            # Адаптивный padding
            if face_width > 200:
                adaptive_padding = face_padding_percent * 0.85
            elif face_width < 100:
                adaptive_padding = face_padding_percent * 1.25
            else:
                adaptive_padding = face_padding_percent
            
            padding_x = int(face_width * adaptive_padding)
            padding_y = int(face_height * adaptive_padding)
            
            # Овал лица
            if use_oval_shape:
                rw = (face_width // 2) * 0.85 + padding_x
                rh = (face_height // 2) * 0.90 + padding_y
            else:
                rw = face_width // 2 + padding_x
                rh = face_height // 2 + padding_y
            
            # Сдвиг центра вверх
            adjusted_cy = cy - int(face_height * 0.08)
            
            # Рисуем овал (чёрный = сохранить)
            draw.ellipse([
                cx - rw, adjusted_cy - rh,
                cx + rw, adjusted_cy + rh
            ], fill=0)
            
            # Градиентные слои для плавного перехода
            for i in range(1, 6):
                gray = int(50 * i)
                extra = i * 6
                draw.ellipse([
                    cx - rw - extra, adjusted_cy - rh - extra,
                    cx + rw + extra, adjusted_cy + rh + extra
                ], fill=gray)
                
        else:
            # Fallback эвристика
            if height > width:
                face_w = int(width * 0.45)
                face_h = int(height * 0.35)
                face_x = (width - face_w) // 2
                face_y = int(height * 0.08)
            else:
                face_w = int(width * 0.40)
                face_h = int(height * 0.48)
                face_x = (width - face_w) // 2
                face_y = int(height * 0.10)
            
            draw.ellipse([face_x-30, face_y-30, face_x+face_w+30, face_y+face_h+30], fill=0)
            
            for i in range(1, 6):
                gray = int(50 * i)
                draw.ellipse([
                    face_x-30-i*6, face_y-30-i*6,
                    face_x+face_w+30+i*6, face_y+face_h+30+i*6
                ], fill=gray)
        
        # Размытие
        if blur_radius > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Статистика и корректировка
        mask_data = list(mask.getdata())
        protected = sum(1 for p in mask_data if p < 255)
        percent = (protected / len(mask_data)) * 100
        
        if percent < 15 or percent > 35:
            mask = Image.new("L", (width, height), 255)
            draw = ImageDraw.Draw(mask)
            draw.ellipse([width*0.25, height*0.08, width*0.75, height*0.45], fill=0)
            for i in range(1, 6):
                gray = int(50 * i)
                draw.ellipse([
                    width*0.25-i*8, height*0.08-i*8,
                    width*0.75+i*8, height*0.45+i*8
                ], fill=gray)
            mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
        
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()
        
    except Exception as e:
        logger.error(f"❌ Mask creation error: {e}")
        # Fallback маска
        mask = Image.new("L", (512, 512), 255)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([128, 40, 384, 230], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()


# =============================================================================
# 📸 TEXT-TO-IMAGE (FLUX)
# =============================================================================

async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Text-to-Image через FLUX.1 Schnell"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = {
        k: v for k, v in {
            "prompt": prompt.strip(),
            "width": width,
            "height": height,
            "steps": 4,
            "negative_prompt": negative_prompt.strip() if negative_prompt else None
        }.items() if v is not None
    }
    
    logger.info(f"📡 text-to-image: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            logger.info(f"✅ FLUX success: {len(resp.content)} bytes")
            return resp.content
        except Exception as e:
            logger.error(f"❌ FLUX error: {e}")
            return None


# =============================================================================
# 🎨 INPAINTING FOR PHOTOSHOOT
# =============================================================================

async def generate_inpainting_photoshoot(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.95,
    guidance: float = 10.0,
    steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Inpainting фотосессия с маской лица"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # Сжимаем исходное изображение
    compressed = _compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # Получаем размеры для маски
    img = Image.open(io.BytesIO(compressed))
    w, h = img.size
    
    # Детекция лица
    face_bbox = await detect_face_via_space(compressed)
    
    # Создаём маску
    mask_bytes = create_inpainting_mask(
        compressed,
        face_bbox,
        width=w,
        height=h
    )
    mask_b64 = base64.b64encode(mask_bytes).decode()
    
    # Формируем payload
    payload = {
        k: v for k, v in {
            "prompt": prompt.strip(),
            "image_b64": image_b64,
            "mask_b64": mask_b64,
            "width": width,
            "height": height,
            "strength": strength,
            "guidance_scale": guidance,
            "num_steps": min(20, max(10, int(steps))),
            "negative_prompt": negative_prompt.strip() if negative_prompt else None
        }.items() if v is not None
    }
    
    logger.info(f"🚀 Inpainting request: {len(compressed)}B img, {len(mask_bytes)}B mask")
    
    async with httpx.AsyncClient(timeout=120) as client:
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
