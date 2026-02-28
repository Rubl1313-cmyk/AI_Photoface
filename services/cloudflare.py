# services/cloudflare.py
import httpx
import base64
import logging
import json
import os
from typing import Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFilter
import io

logger = logging.getLogger(__name__)

# =============================================================================
# 🔑 КОНСТАНТЫ
# =============================================================================
MAX_IMAGE_KB = 400
MAX_DIMENSION = 512
JPEG_QUALITY = 90

# 🔑 URL вашего Space для детекции лица (уже работает!)
FACE_DETECT_SPACE_URL = os.getenv(
    "FACE_DETECT_SPACE_URL",
    "https://dmitry1313-face-swaper.hf.space/detect"
)
FACE_DETECT_SECRET = os.getenv("FACE_DETECT_SECRET", "")

# =============================================================================
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _compress_image(
    image_bytes: bytes,
    max_dimension: int = MAX_DIMENSION,
    max_kb: int = MAX_IMAGE_KB,
    quality: int = JPEG_QUALITY
) -> bytes:
    """
    Сжимает изображение для отправки в API:
    - Ресайз до max_dimension
    - JPEG сжатие до max_kb
    """
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


def _no_none(data: Dict[str, Any]) -> Dict[str, Any]:
    """Удаляет ключи со значением None из словаря"""
    return {k: v for k, v in data.items() if v is not None}


def truncate_caption(text: str, max_length: int = 1024, suffix: str = "...") -> str:
    """
    🔑 Обрезает текст до лимита Telegram caption (1024 символа)
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# =============================================================================
# 🔍 DETECT FACE VIA CUSTOM HF SPACE
# =============================================================================

async def detect_face_via_space(image_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    🔥 Детекция лица через ваш приватный Space на Hugging Face
    
    Возвращает:
        {
            "x": int, "y": int,
            "width": int, "height": int,
            "score": float,
            "image_width": int, "image_height": int
        }
        или None если лицо не найдено / ошибка
    """
    if not FACE_DETECT_SPACE_URL:
        logger.warning("⚠️ FACE_DETECT_SPACE_URL not set")
        return None
    
    try:
        # 🔑 Увеличенный таймаут для cold start Space (до 120 сек)
        async with httpx.AsyncClient(timeout=120.0) as client:
            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
            headers = {}
            if FACE_DETECT_SECRET:
                headers["Authorization"] = f"Bearer {FACE_DETECT_SECRET}"
            
            logger.info(f"🔍 Requesting face detection from Space...")
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
                    logger.info(
                        f"✅ Face detected via Space: "
                        f"{face['width']}x{face['height']}px @ ({face['x']},{face['y']}), "
                        f"score={face['score']:.3f}"
                    )
                    return {
                        "x": face["x"],
                        "y": face["y"],
                        "width": face["width"],
                        "height": face["height"],
                        "score": face["score"],
                        "image_width": img_size.get("width"),
                        "image_height": img_size.get("height")
                    }
                else:
                    logger.warning(f"⚠️ Space: {result.get('error', 'No face detected')}")
            elif response.status_code == 404:
                logger.warning("⚠️ Space returned 404: No face detected")
            else:
                logger.error(f"❌ Space API error {response.status_code}: {response.text[:200]}")
                
    except httpx.TimeoutException:
        logger.error("❌ Space API timeout (cold start?)")
    except httpx.RequestError as e:
        logger.error(f"❌ Space API request error: {e}")
    except Exception as e:
        logger.error(f"❌ Space API unexpected error: {type(e).__name__}: {e}")
    
    return None


# =============================================================================
# 🎭 MASK CREATION FOR INPAINTING
# =============================================================================

def create_inpainting_mask(
    image_bytes: bytes,
    face_bbox: Optional[Dict[str, int]],
    width: int,
    height: int,
    face_padding_percent: float = 0.20,  # ← Увеличил с 0.15 до 0.20
    blur_radius: int = 15,                # ← Увеличил с 12 до 15
    use_face_mesh: bool = True            # ← Новый параметр
) -> bytes:
    """
    🔥 УЛУЧШЕННАЯ маска для inpainting:
    - Точный овал лица (не просто прямоугольник)
    - Адаптивный padding
    - Плавные границы
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        
        mask = Image.new("L", (w, h), 255)  # Белый = менять фон
        draw = ImageDraw.Draw(mask)
        
        if face_bbox and face_bbox.get("width", 0) > 20:
            cx = face_bbox["x"] + face_bbox["width"] // 2
            cy = face_bbox["y"] + face_bbox["height"] // 2
            
            # 🔑 УЛУЧШЕНИЕ 1: Эллипс вместо прямоугольника
            # Учитываем пропорции лица
            face_width = face_bbox["width"]
            face_height = face_bbox["height"]
            
            # 🔑 УЛУЧШЕНИЕ 2: Адаптивный padding
            # Для крупных лиц меньше padding, для мелких - больше
            base_padding = face_padding_percent
            if face_width > 200:  # Крупное лицо
                adaptive_padding = base_padding * 0.8
            elif face_width < 100:  # Мелкое лицо
                adaptive_padding = base_padding * 1.3
            else:
                adaptive_padding = base_padding
            
            padding_x = int(face_width * adaptive_padding)
            padding_y = int(face_height * adaptive_padding)
            
            # 🔑 УЛУЧШЕНИЕ 3: Овал лица (уже чем bounding box)
            # Лицо обычно уже чем bbox на 10-15%
            rw = (face_width // 2) * 0.85 + padding_x
            rh = (face_height // 2) * 0.90 + padding_y
            
            # Сдвигаем центр немного вверх (лицо выше центра bbox)
            adjusted_cy = cy - (face_height * 0.10)
            
            # Рисуем точный овал лица
            draw.ellipse([
                cx - rw, adjusted_cy - rh,
                cx + rw, adjusted_cy + rh
            ], fill=0)
            
            # 🔑 УЛУЧШЕНИЕ 4: Многослойный градиент (5 слоёв вместо 2)
            for i in range(1, 6):
                gray = int(50 * i)  # 50, 100, 150, 200, 250
                extra = i * 6
                draw.ellipse([
                    cx - rw - extra, adjusted_cy - rh - extra,
                    cx + rw + extra, adjusted_cy + rh + extra
                ], fill=gray)
            
            logger.info(f"🎯 Precise face mask: {rw*2:.0f}x{rh*2:.0f}, padding={adaptive_padding:.1%}")
            
        else:
            # Fallback эвристика (улучшенная)
            if h > w:
                face_w = int(w * 0.45)
                face_h = int(h * 0.35)
                face_x = (w - face_w) // 2
                face_y = int(h * 0.08)
            else:
                face_w = int(w * 0.40)
                face_h = int(h * 0.48)
                face_x = (w - face_w) // 2
                face_y = int(h * 0.10)
            
            draw.ellipse([face_x-30, face_y-30, face_x+face_w+30, face_y+face_h+30], fill=0)
            for i in range(1, 6):
                gray = int(50 * i)
                draw.ellipse([face_x-30-i*6, face_y-30-i*6, face_x+face_w+30+i*6, face_y+face_h+30+i*6], fill=gray)
        
        # 🔑 УЛУЧШЕНИЕ 5: Сильное размытие (radius=15 вместо 12)
        if blur_radius > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Статистика
        mask_data = list(mask.getdata())
        protected = sum(1 for p in mask_data if p < 128)
        percent = (protected / len(mask_data)) * 100
        logger.info(f"🎭 Mask: {percent:.1f}% protected (target: 18-22%)")
        
        # Корректировка если вышла за пределы
        if percent < 15 or percent > 28:
            logger.warning(f"⚠️ Mask {percent:.1f}% out of range, adjusting...")
            mask = Image.new("L", (w, h), 255)
            draw = ImageDraw.Draw(mask)
            draw.ellipse([w*0.25, h*0.08, w*0.75, h*0.45], fill=0)
            for i in range(1, 6):
                gray = int(50 * i)
                draw.ellipse([w*0.25-i*8, h*0.08-i*8, w*0.75+i*8, h*0.45+i*8], fill=gray)
            mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
        
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()
        
    except Exception as e:
        logger.error(f"❌ Mask error: {e}")
        # Fallback
        mask = Image.new("L", (512, 512), 255)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([512*0.25, 512*0.08, 512*0.75, 512*0.45], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=15))
        out = io.BytesIO()
        mask.save(out, format="PNG")
        return out.getvalue()

# =============================================================================
# 📸 TEXT-TO-IMAGE (FLUX) — НЕ ТРОГАЕМ, работает как было
# =============================================================================

async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    Text-to-Image генерация через FLUX.1 Schnell
    (используется для "Просто генерация" и как первый шаг для "С заменой лица")
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    payload = _no_none({
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "steps": 4,
        "negative_prompt": negative_prompt.strip() if negative_prompt else None,
    })
    
    logger.info(f"📡 text-to-image: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            logger.info(f"✅ FLUX success: {len(resp.content)} bytes")
            return resp.content
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"❌ FLUX error: {type(e).__name__}: {e}")
            return None


# =============================================================================
# 🎨 INPAINTING ДЛЯ «ИИ ФОТОСЕССИИ»
# =============================================================================

async def generate_inpainting_photoshoot(
    prompt: str,
    source_image_bytes: bytes,
    width: int = 512,
    height: int = 512,
    strength: float = 0.95,      # 🔑 Высокий strength для изменения фона
    guidance: float = 10.0,      # 🔑 Высокий guidance для строгого следования промпту
    steps: int = 20,             # 🔑 Максимум для inpainting модели Cloudflare
    negative_prompt: str = ""
) -> Optional[bytes]:
    """
    🎭 Inpainting фотосессия:
    1. Сжимаем исходное изображение
    2. 🔍 Детектируем лицо через ваш HF Space
    3. 🎨 Создаём маску (лицо=чёрное, фон=белое)
    4. ☁️ Отправляем в Cloudflare inpainting модель
    5. ✅ Возвращаем результат
    
    Результат: лицо сохранено, фон изменён по промпту
    """
    url = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()
    
    # 1. 🔧 Сжимаем исходное изображение
    compressed = _compress_image(source_image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    
    # Получаем размеры для маски
    img = Image.open(io.BytesIO(compressed))
    w, h = img.size
    
    # 2. 🔍 Детекция лица через ваш Space
    logger.info("🔍 Detecting face via custom HF Space...")
    face_bbox = await detect_face_via_space(compressed)
    
    if face_bbox:
        logger.info(f"✅ Face: {face_bbox['width']}x{face_bbox['height']}px, score={face_bbox['score']:.3f}")
    else:
        logger.warning("⚠️ Face not detected by Space, using heuristic mask")
    
    # 3. 🎨 Создаём маску
    mask_bytes = create_inpainting_mask(
        compressed,
        face_bbox,
        width=w,
        height=h,
        face_padding_percent=0.15,  # 15% padding
        blur_radius=12
    )
    mask_b64 = base64.b64encode(mask_bytes).decode()
    
    # 4. ☁️ Формируем payload для Cloudflare
    safe_steps = min(20, max(10, int(steps)))  # 10-20 диапазон
    
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
    
    logger.info(f"🚀 Inpainting request: {len(compressed)}B img, {len(mask_bytes)}B mask")
    
    # 5. ✅ Отправляем в Cloudflare
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


# =============================================================================
# 🔄 FACE SWAP ПОСЛЕ FLUX (для режима "С заменой лица")
# =============================================================================

async def swap_face_after_flux(
    flux_image_bytes: bytes,
    source_face_bytes: bytes,
    facefusion_url: str
) -> Optional[bytes]:
    """
    🔁 Замена лица на сгенерированном FLUX изображении через FaceFusion API
    
    Используется в режиме "С заменой лица":
    1. FLUX генерирует изображение по промпту
    2. FaceFusion заменяет лицо на сгенерированном изображении на лицо пользователя
    """
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            files = {
                "target": ("target.jpg", flux_image_bytes, "image/jpeg"),
                "source": ("source.jpg", source_face_bytes, "image/jpeg")
            }
            
            logger.info(f"🔄 Sending to FaceFusion: {len(flux_image_bytes)}B target, {len(source_face_bytes)}B source")
            
            response = await client.post(
                f"{facefusion_url}/swap",
                files=files
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Face swap success: {len(response.content)} bytes")
                return response.content
            else:
                logger.error(f"❌ FaceFusion error {response.status_code}: {response.text[:200]}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Face swap error: {type(e).__name__}: {e}")
        return None
