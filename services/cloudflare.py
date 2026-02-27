# services/cloudflare.py
import httpx
import base64
import logging
import asyncio
import json
import os
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFilter
import io

logger = logging.getLogger(__name__)

# 🔑 Константы
MAX_IMAGE_KB = 400
MAX_DIMENSION = 512
JPEG_QUALITY = 90

# 🔑 Hugging Face Token (читается из env)
HF_TOKEN = os.getenv("HF_TOKEN", "")

# 🔑 Fallback-цепочка моделей для детекции лица (по приоритету)
HF_FACE_MODELS = [
    "amd/retinaface",              # 🥇 RetinaFace — SOTA точность
    "py-feat/retinaface",          # 🥈 Альтернативный RetinaFace
    "opencv/face_detection_yunet", # 🥉 YuNet — лёгкий и быстрый
    "facebook/detr-resnet-50",     # 🔄 DETR — object detection как запасной
]


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


async def _try_hf_model(
    client: httpx.AsyncClient,
    model_name: str,
    image_bytes: bytes
) -> Optional[Dict[str, int]]:
    """
    Пробует одну модель HF API.
    Возвращает bbox {x, y, width, height} или None.
    """
    try:
        # Формируем URL: некоторые модели требуют полного пути
        if model_name.startswith("http"):
            url = model_name
        else:
            url = f"https://api-inference.huggingface.co/models/{model_name}"
        
        logger.debug(f"🔍 Trying HF model: {model_name}")
        
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            content=image_bytes,
            timeout=25.0
        )
        
        if resp.status_code == 200:
            result = resp.json()
            
            # 🎯 RetinaFace формат: {"boxes": [[x1,y1,x2,y2]], "scores": [...]}
            if isinstance(result, dict) and "boxes" in result and result["boxes"]:
                x1, y1, x2, y2 = result["boxes"][0]
                return {"x": int(x1), "y": int(y1), "width": int(x2-x1), "height": int(y2-y1)}
            
            # 🎯 DETR формат: [{"label":"person","score":0.99,"box":{"xmin":..,"ymin":..,"xmax":..,"ymax":..}}]
            if isinstance(result, list) and result:
                item = result[0]
                if "box" in item:
                    box = item["box"]
                    return {
                        "x": int(box.get("xmin", 0)),
                        "y": int(box.get("ymin", 0)),
                        "width": int(box.get("xmax", 0) - box.get("xmin", 0)),
                        "height": int(box.get("ymax", 0) - box.get("ymin", 0))
                    }
                # Простой формат [x1,y1,x2,y2]
                if isinstance(item, (list, tuple)) and len(item) == 4:
                    x1, y1, x2, y2 = item
                    return {"x": int(x1), "y": int(y1), "width": int(x2-x1), "height": int(y2-y1)}
            
            logger.debug(f"⚠️ Model {model_name} returned unexpected format: {type(result)}")
            return None
            
        elif resp.status_code == 503:
            logger.debug(f"⏳ Model {model_name} is loading...")
            return None  # Попробуем следующую
        else:
            logger.debug(f"⚠️ Model {model_name} failed: {resp.status_code}")
            return None
            
    except Exception as e:
        logger.debug(f"⚠️ Model {model_name} error: {type(e).__name__}: {e}")
        return None


async def detect_face_with_fallback(image_bytes: bytes) -> Optional[Dict[str, int]]:
    """
    🔁 Пробует все модели из HF_FACE_MODELS по очереди.
    Если все HF API не сработали — возвращает None (будет использована эвристика).
    """
    if not HF_TOKEN:
        logger.warning("⚠️ HF_TOKEN not set, skipping HF face detection")
        return None
    
    async with httpx.AsyncClient() as client:
        for model in HF_FACE_MODELS:
            result = await _try_hf_model(client, model, image_bytes)
            if result:
                logger.info(f"✅ Face detected via {model}: {result}")
                return result
    
    logger.warning("⚠️ All HF models failed, will use heuristic fallback")
    return None


def detect_face_mediapipe(image_bytes: bytes) -> Optional[Dict[str, int]]:
    """
    🔄 Локальная детекция лица через MediaPipe (fallback если HF API недоступен)
    Требует: mediapipe>=0.10.0, opencv-python-headless>=4.8.0
    """
    try:
        import mediapipe as mp
        import cv2
        import numpy as np
        
        mp_face_detection = mp.solutions.face_detection
        
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return None
        
        with mp_face_detection.FaceDetection(min_detection_confidence=0.5) as face_detection:
            results = face_detection.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            
            if results.detections:
                detection = results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                h, w = img.shape[:2]
                
                return {
                    "x": max(0, int(bbox.xmin * w)),
                    "y": max(0, int(bbox.ymin * h)),
                    "width": min(w, int(bbox.width * w)),
                    "height": min(h, int(bbox.height * h))
                }
    except ImportError:
        logger.debug("⚠️ MediaPipe not installed, skipping local detection")
    except Exception as e:
        logger.debug(f"⚠️ MediaPipe error: {e}")
    
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
        
        if bbox and bbox.get("width", 0) > 20 and bbox.get("height", 0) > 20:
            # Рисуем чёрный овал на месте детектированного лица
            cx = bbox["x"] + bbox["width"] // 2
            cy = bbox["y"] + bbox["height"] // 2
            rw = bbox["width"] // 2 + padding
            rh = bbox["height"] // 2 + padding
            draw.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=0)
        else:
            # 🔑 Fallback эвристика: верхняя центральная часть (где обычно лицо)
            fw, fh = int(w * 0.65), int(h * 0.6)
            fx, fy = (w - fw) // 2, int(h * 0.12)
            draw.ellipse([fx-padding, fy-padding, fx+fw+padding, fy+fh+padding], fill=0)
        
        # 🔑 ИСПРАВЛЕНО: ImageFilter.GaussianBlur
        if blur > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur))
        
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        logger.error(f"❌ Mask creation error: {e}")
        fallback = Image.new("L", (512, 512), 255)
        fb_out = io.BytesIO()
        fallback.save(fb_out, format="PNG")
        return fb_out.getvalue()


def _no_none( Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет None значения из dict"""
    return {k: v for k, v in data.items() if v is not None}


# =============================================================================
# TEXT-TO-IMAGE (FLUX) — без изменений, работает как было
# =============================================================================
async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """Text-to-Image через FLUX.1 Schnell"""
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
    steps: int = 20,  # 🔑 Максимум 20 для inpainting модели Cloudflare
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    🎭 Inpainting для фотосессии:
    1. Детектируем лицо (HF API fallback chain → MediaPipe → эвристика)
    2. Создаём маску (лицо=чёрное, фон=белое)
    3. Отправляем в Cloudflare inpainting модель
    4. Возвращаем результат
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # 1. Сжимаем исходное изображение
    compressed = _compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # 2. 🔁 Детекция лица с fallback-цепочкой
    logger.info("🔍 Detecting face: HF models → MediaPipe → heuristic...")
    
    # Попытка через HF API
    bbox = await detect_face_with_fallback(compressed)
    
    # Если HF не сработал — пробуем MediaPipe локально
    if not bbox:
        logger.info("🔄 Trying MediaPipe local detection...")
        bbox = detect_face_mediapipe(compressed)
        if bbox:
            logger.info(f"✅ Face detected via MediaPipe: {bbox}")
    
    # Если всё ещё нет — используем эвристику
    if bbox:
        logger.info(f"✅ Face found: {bbox}")
    else:
        logger.warning("⚠️ Face not detected, using fallback heuristic mask")
    
    # 3. Создаём маску
    mask_bytes = create_inpainting_mask(compressed, bbox)
    mask_b64 = base64.b64encode(mask_bytes).decode()
    logger.info(f"🎭 Mask: {len(mask_bytes)} bytes")
    
    # 4. Формируем payload для Cloudflare
    # 🔑 num_steps: 10-20 для inpainting модели
    safe_steps = min(20, max(10, int(steps)))
    
    payload = _no_none({
        "prompt": prompt.strip(),
        "image_b64": image_b64,
        "mask_b64": mask_b64,  # ← 🔑 КЛЮЧЕВОЕ: маска для inpainting
        "width": width,
        "height": height,
        "strength": strength,
        "guidance_scale": guidance,
        "num_steps": safe_steps,
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
