# services/cloudflare.py
import httpx
import base64
import logging
import asyncio
import json
import os
from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFilter
import io
import numpy as np

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
    """Сжимает изображение для отправки в Cloudflare"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        w, h = img.size
        if w > max_dimension or h > max_dimension:
            ratio = min(max_dimension / w, max_dimension / h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
            logger.info(f"📐 Resized: {w}x{h} → {img.size[0]}x{img.size[1]}")
        
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


def detect_face_mediapipe_precise(image_bytes: bytes) -> Optional[Dict[str, int]]:
    """
    🔥 Детекция лица через MediaPipe 0.10.13+
    Возвращает bbox {x, y, width, height} или None
    """
    try:
        # 🔑 ПРАВИЛЬНЫЙ импорт для mediapipe>=0.10.13
        import mediapipe as mp
        import cv2
        
        # Конвертируем bytes → numpy array
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error("❌ Failed to decode image")
            return None
        
        h, w = img.shape[:2]
        logger.info(f"📐 Image loaded: {w}x{h}px")
        
        # 🔑 Используем solutions API (всё ещё работает в 0.10.x)
        mp_face_detection = mp.solutions.face_detection
        
        with mp_face_detection.FaceDetection(
            min_detection_confidence=0.5,
            model_selection=1  # 1=full-range для общих фото
        ) as face_detection:
            # 🔑 BGR → RGB (MediaPipe требует RGB)
            rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb_image)
            
            if results.detections:
                # Выбираем самое крупное лицо
                faces = []
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    score = detection.score[0] if detection.score else 0
                    
                    # Абсолютные координаты
                    x = max(0, int(bbox.xmin * w))
                    y = max(0, int(bbox.ymin * h))
                    width = min(w - x, int(bbox.width * w))
                    height = min(h - y, int(bbox.height * h))
                    area = width * height
                    
                    faces.append({
                        "x": x, "y": y, "width": width, "height": height,
                        "score": score, "area": area
                    })
                    logger.debug(f"  Face: {width}x{height}px, score={score:.2f}")
                
                # 🔑 Берём самое крупное по площади
                best = max(faces, key=lambda f: f["area"])
                logger.info(f"✅ Face detected: {best['width']}x{best['height']}px, score={best['score']:.2f}")
                
                return {
                    "x": best["x"], "y": best["y"],
                    "width": best["width"], "height": best["height"],
                    "score": best["score"]
                }
            else:
                logger.warning("⚠️ MediaPipe: no faces detected")
                return None
                
    except ImportError as e:
        logger.error(f"❌ MediaPipe import error: {e}")
        return None
    except AttributeError as e:
        # 🔑 Обработка ошибки 'module has no attribute solutions'
        logger.error(f"❌ MediaPipe API changed: {e}")
        logger.error("💡 Try: pip install 'mediapipe<0.11' or use fallback heuristic")
        return None
    except Exception as e:
        logger.error(f"❌ MediaPipe runtime error: {type(e).__name__}: {e}")
        return None

def create_inpainting_mask_precise(
    image_bytes: bytes,
    bbox: Optional[Dict[str, int]],
    face_padding_percent: float = 0.40,
    blur_radius: int = 18
) -> bytes:
    """
    🔥 Надёжная маска: работает даже без детекции лица
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        mask = Image.new("L", (w, h), 255)  # Белый = менять фон
        draw = ImageDraw.Draw(mask)
        
        if bbox and bbox.get("width", 0) > 25 and bbox.get("height", 0) > 25:
            # 🔑 Использовать детектированное лицо
            cx = bbox["x"] + bbox["width"] // 2
            cy = bbox["y"] + bbox["height"] // 2
            padding_x = int(bbox["width"] * face_padding_percent)
            padding_y = int(bbox["height"] * face_padding_percent)
            rw = bbox["width"] // 2 + padding_x
            rh = bbox["height"] // 2 + padding_y
            
            draw.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=0)
            
            # Плавный градиентный переход
            for i in range(1, 5):
                alpha = int(50 * i)
                draw.ellipse([cx-rw-i*6, cy-rh-i*6, cx+rw+i*6, cy+rh+i*6], fill=alpha)
                
        else:
            # 🔥 УЛУЧШЕННАЯ эвристика для портретов
            # Адаптируется под соотношение сторон изображения
            
            if h > w * 1.3:  # Вертикальное (портрет)
                face_w = int(w * 0.58)   # Лицо занимает ~58% ширины
                face_h = int(h * 0.45)   # и ~45% высоты
                face_x = (w - face_w) // 2
                face_y = int(h * 0.05)   # 5% от верха
                padding = 60
                
            elif w > h * 1.3:  # Горизонтальное
                face_w = int(w * 0.38)
                face_h = int(h * 0.68)
                face_x = (w - face_w) // 2
                face_y = int(h * 0.10)
                padding = 50
                
            else:  # Квадратное
                face_w = int(w * 0.52)
                face_h = int(h * 0.50)
                face_x = (w - face_w) // 2
                face_y = int(h * 0.08)
                padding = 55
            
            # Рисуем основной овал (чёрный = сохранить)
            draw.ellipse([
                face_x - padding,
                face_y - padding,
                face_x + face_w + padding,
                face_y + face_h + padding
            ], fill=0)
            
            # Градиентные слои для плавного перехода
            for i in range(1, 7):
                alpha = int(35 * i)
                draw.ellipse([
                    face_x - padding - i*5,
                    face_y - padding - i*5,
                    face_x + face_w + padding + i*5,
                    face_y + face_h + padding + i*5
                ], fill=alpha)
        
        # 🔑 Сильное размытие для бесшовного перехода
        if blur_radius > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Статистика маски
        mask_data = list(mask.getdata())
        protected = sum(1 for p in mask_data if p < 100)
        logger.info(f"🎭 Mask: {protected/len(mask_data)*100:.1f}% protected area")
        
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()
        
    except Exception as e:
        logger.error(f"❌ Mask error: {e}")
        fallback = Image.new("L", (512, 512), 255)
        fb_out = io.BytesIO()
        fallback.save(fb_out, format="PNG")
        return fb_out.getvalue()

# ✅ ИСПРАВЛЕНО: параметр называется 'data'
def _no_none(data: Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет None значения из dict"""
    return {k: v for k, v in data.items() if v is not None}


# =============================================================================
# TEXT-TO-IMAGE (FLUX) — без изменений
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
    negative_prompt: str = "",
    face_padding: float = 0.35
) -> Optional[bytes]:
    """Inpainting фотосессия с MediaPipe детекцией"""
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # 1. Сжимаем изображение
    compressed = _compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # 2. Детекция лица через MediaPipe
    logger.info("🔍 Detecting face with MediaPipe...")
    bbox = detect_face_mediapipe_precise(compressed)
    
    if bbox:
        logger.info(f"✅ Face: {bbox['width']}x{bbox['height']}px, score={bbox['score']:.2f}")
    else:
        logger.warning("⚠️ Face not detected, using heuristic mask")
    
    # 3. Создаём маску
    mask_bytes = create_inpainting_mask_precise(compressed, bbox, face_padding_percent=face_padding)
    mask_b64 = base64.b64encode(mask_bytes).decode()
    
    # 4. Формируем payload
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
    
    logger.info(f"🚀 Inpainting request: {len(json.dumps(payload))/1024:.1f}KB")
    
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
