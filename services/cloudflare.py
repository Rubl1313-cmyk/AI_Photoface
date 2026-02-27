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
    🔥 ТОЧНАЯ детекция лица через MediaPipe
    Возвращает bbox {x, y, width, height} или None
    """
    try:
        import mediapipe as mp
        import cv2
        
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error("❌ Failed to decode image")
            return None
        
        h, w = img.shape[:2]
        logger.info(f"📐 Image loaded: {w}x{h}px")
        
        mp_face_detection = mp.solutions.face_detection
        
        with mp_face_detection.FaceDetection(
            min_detection_confidence=0.5,
            model_selection=1
        ) as face_detection:
            rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb_image)
            
            if results.detections:
                faces = []
                for i, detection in enumerate(results.detections):
                    bbox = detection.location_data.relative_bounding_box
                    score = detection.score[0] if detection.score else 0
                    
                    x = max(0, int(bbox.xmin * w))
                    y = max(0, int(bbox.ymin * h))
                    width = min(w - x, int(bbox.width * w))
                    height = min(h - y, int(bbox.height * h))
                    area = width * height
                    
                    faces.append({
                        "x": x, "y": y, "width": width, "height": height,
                        "score": score, "area": area
                    })
                    logger.info(f"  Face {i+1}: {width}x{height}px, score={score:.2f}")
                
                best_face = max(faces, key=lambda f: f["area"])
                logger.info(f"✅ Selected best face: {best_face['width']}x{best_face['height']}px")
                
                return {
                    "x": best_face["x"], "y": best_face["y"],
                    "width": best_face["width"], "height": best_face["height"],
                    "score": best_face["score"]
                }
            else:
                logger.warning("⚠️ MediaPipe: no faces detected")
                return None
                
    except ImportError as e:
        logger.error(f"❌ MediaPipe not installed: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ MediaPipe error: {type(e).__name__}: {e}")
        return None


def create_inpainting_mask_precise(
    image_bytes: bytes,
    bbox: Optional[Dict[str, int]],
    face_padding_percent: float = 0.35,
    blur_radius: int = 15
) -> bytes:
    """
    🔥 ТОЧНАЯ маска: ⚫ чёрный = сохранить, ⚪ белый = изменить
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        mask = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(mask)
        
        if bbox and bbox.get("width", 0) > 20 and bbox.get("height", 0) > 20:
            cx = bbox["x"] + bbox["width"] // 2
            cy = bbox["y"] + bbox["height"] // 2
            padding_x = int(bbox["width"] * face_padding_percent)
            padding_y = int(bbox["height"] * face_padding_percent)
            rw = bbox["width"] // 2 + padding_x
            rh = bbox["height"] // 2 + padding_y
            
            logger.info(f"🎯 Face mask: center=({cx},{cy}), radius=({rw},{rh})")
            draw.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=0)
            
            # Плавный переход
            for i in range(1, 4):
                alpha = int(64 * i)
                rw2 = rw + (i * 5)
                rh2 = rh + (i * 5)
                draw.ellipse([cx-rw2, cy-rh2, cx+rw2, cy+rh2], fill=alpha)
        else:
            # Fallback эвристика
            if h > w:
                face_w, face_h = int(w * 0.60), int(h * 0.50)
                face_x, face_y = (w - face_w) // 2, int(h * 0.08)
            else:
                face_w, face_h = int(w * 0.50), int(h * 0.60)
                face_x, face_y = (w - face_w) // 2, int(h * 0.10)
            
            draw.ellipse([face_x-50, face_y-50, face_x+face_w+50, face_y+face_h+50], fill=0)
        
        if blur_radius > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Статистика
        mask_array = list(mask.getdata())
        black = sum(1 for p in mask_array if p < 64)
        total = len(mask_array)
        logger.info(f"🎭 Mask: {black/total*100:.1f}% black (face area)")
        
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
def _no_none( Dict[str, Any]) -> Dict[str, Any]:
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
