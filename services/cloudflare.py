# services/cloudflare.py
import httpx
import base64
import logging
import json
import os
from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFilter
import io
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# 🔑 Константы
MAX_IMAGE_KB = 400
MAX_DIMENSION = 512
JPEG_QUALITY = 90


def _compress_image(
    image_bytes: bytes,
    max_dimension: int = MAX_DIMENSION,
    max_kb: int = MAX_IMAGE_KB,
    quality: int = JPEG_QUALITY
) -> bytes:
    """Сжимает изображение"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        w, h = img.size
        if w > max_dimension or h > max_dimension:
            ratio = min(max_dimension / w, max_dimension / h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"📐 Resized: {w}x{h} → {new_size[0]}x{new_size[1]}")
        
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


def detect_face_mediapipe(image_bytes: bytes) -> Optional[Dict[str, int]]:
    """
    🔥 Детекция лица через MediaPipe 0.10.32
    ПРАВИЛЬНЫЙ импорт и использование
    """
    try:
        # 🔑 ПРАВИЛЬНЫЙ импорт для MediaPipe
        import mediapipe as mp
        
        # Конвертируем bytes → numpy → OpenCV
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error("❌ Failed to decode image")
            return None
        
        h, w = img.shape[:2]
        logger.info(f"📐 Image loaded: {w}x{h}px")
        
        # 🔑 ПРАВИЛЬНОЕ использование mp.solutions.face_detection
        mp_face_detection = mp.solutions.face_detection
        
        # 🔑 model_selection=1 для full-range (до 5 метров)
        with mp_face_detection.FaceDetection(
            model_selection=1,  # 0=short-range (2m), 1=full-range (5m)
            min_detection_confidence=0.5
        ) as face_detection:
            # 🔑 BGR → RGB (MediaPipe требует RGB!)
            rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb_image)
            
            if results.detections:
                # Берём первое (самое крупное) лицо
                detection = results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                
                # Относительные → абсолютные координаты
                x = max(0, int(bbox.xmin * w))
                y = max(0, int(bbox.ymin * h))
                width = min(w - x, int(bbox.width * w))
                height = min(h - y, int(bbox.height * h))
                
                score = detection.score[0] if detection.score else 0
                
                logger.info(f"✅ Face detected: {width}x{height}px, score={score:.2f}")
                
                return {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "score": score
                }
            else:
                logger.warning("⚠️ No faces detected")
                return None
                
    except AttributeError as e:
        logger.error(f"❌ MediaPipe API error: {e}")
        logger.error("💡 Check: pip install mediapipe==0.10.32")
        return None
    except ImportError as e:
        logger.error(f"❌ MediaPipe not installed: {e}")
        logger.error("💡 Install: pip install mediapipe==0.10.32 opencv-python-headless numpy")
        return None
    except Exception as e:
        logger.error(f"❌ MediaPipe error: {type(e).__name__}: {e}")
        return None


def create_inpainting_mask(
    image_bytes: bytes,
    bbox: Optional[Dict[str, int]],
    padding_percent: float = 0.40,
    blur_radius: int = 18
) -> bytes:
    """
    🔥 Создаёт маску для inpainting
    ⚫ Чёрный (0) = сохранить (лицо)
    ⚪ Белый (255) = изменить (фон)
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        mask = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(mask)
        
        if bbox and bbox.get("width", 0) > 20:
            # Используем детектированное лицо
            cx = bbox["x"] + bbox["width"] // 2
            cy = bbox["y"] + bbox["height"] // 2
            padding_x = int(bbox["width"] * padding_percent)
            padding_y = int(bbox["height"] * padding_percent)
            rw = bbox["width"] // 2 + padding_x
            rh = bbox["height"] // 2 + padding_y
            
            # Чёрный овал (сохранить)
            draw.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=0)
            
            # Градиент для плавного перехода
            for i in range(1, 6):
                gray = int(50 * i)
                draw.ellipse([cx-rw-i*6, cy-rh-i*6, cx+rw+i*6, cy+rh+i*6], fill=gray)
                
        else:
            # 🔥 FALLBACK: большая эвристическая маска
            if h > w:  # Портрет
                face_w = int(w * 0.65)
                face_h = int(h * 0.50)
                face_x = (w - face_w) // 2
                face_y = int(h * 0.05)
            else:  # Квадрат/горизонталь
                face_w = int(w * 0.55)
                face_h = int(h * 0.65)
                face_x = (w - face_w) // 2
                face_y = int(h * 0.08)
            
            draw.ellipse([face_x-55, face_y-55, face_x+face_w+55, face_y+face_h+55], fill=0)
            
            for i in range(1, 6):
                gray = int(50 * i)
                draw.ellipse([face_x-55-i*6, face_y-55-i*6, face_x+face_w+55+i*6, face_y+face_h+55+i*6], fill=gray)
        
        # Размытие
        if blur_radius > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Проверка
        data = list(mask.getdata())
        protected = sum(1 for p in data if p < 128)
        percent = (protected / len(data)) * 100
        logger.info(f"🎭 Mask: {percent:.1f}% protected")
        
        if percent < 20:
            logger.error("⚠️ Mask < 20%! Creating emergency mask...")
            mask = Image.new("L", (w, h), 255)
            draw = ImageDraw.Draw(mask)
            draw.ellipse([w*0.15, h*0.05, w*0.85, h*0.60], fill=0)
            mask = mask.filter(ImageFilter.GaussianBlur(radius=25))
        
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()
        
    except Exception as e:
        logger.error(f"❌ Mask error: {e}")
        fallback = Image.new("L", (512, 512), 255)
        fb_out = io.BytesIO()
        fallback.save(fb_out, format="PNG")
        return fb_out.getvalue()


def _no_none( Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет None значения"""
    return {k: v for k, v in data.items() if v is not None}


# =============================================================================
# TEXT-TO-IMAGE (FLUX)
# =============================================================================
async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Text-to-Image через FLUX"""
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
# 🎨 INPAINTING ДЛЯ «ИИ ФОТОСЕССИИ»
# =============================================================================
async def generate_inpainting_photoshoot(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.9,
    guidance: float = 9.5,
    steps: int = 20,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Inpainting фотосессия с MediaPipe детекцией"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # 1. Сжимаем
    compressed = _compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # 2. 🔥 Детекция лица через MediaPipe
    logger.info("🔍 Detecting face with MediaPipe 0.10.32...")
    bbox = detect_face_mediapipe(compressed)
    
    if bbox:
        logger.info(f"✅ Face: {bbox['width']}x{bbox['height']}px, score={bbox['score']:.2f}")
    else:
        logger.warning("⚠️ Face not detected, using heuristic mask")
    
    # 3. Создаём маску
    mask_bytes = create_inpainting_mask(compressed, bbox)
    mask_b64 = base64.b64encode(mask_bytes).decode()
    
    # 4. Payload
    safe_steps = min(20, max(10, int(steps)))
    
    payload = _no_none({
        "prompt": prompt.strip(),
        "image_b64": image_b64,
        "mask_b64": mask_b64,
        "width": width,
        "height": height,
        "strength": strength,
        "guidance_scale": guidance,
        "num_steps": safe_steps,
        "negative_prompt": negative_prompt.strip() if negative_prompt else None,
    })
    
    logger.info(f"🚀 Inpainting: {len(compressed)}B img, {len(mask_bytes)}B mask")
    
    # 5. Отправляем
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
