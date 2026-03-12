# services/cloudflare.py
import base64
import logging
import os
import io
from typing import Optional
from PIL import Image
import aiohttp

logger = logging.getLogger(__name__)

CF_WORKER_URL = os.getenv("CF_WORKER_URL", "https://ai-image-generator.rubl1313.workers.dev").strip()

# Константы моделей
MODEL_SD_V1_5_IMG2IMG = "@cf/runwayml/stable-diffusion-v1-5-img2img"  # для img2img (режимы 1 и 2)
MODEL_FLUX_SCHNELL = "@cf/black-forest-labs/flux-1-schnell"           # для AIMage

# ================== ПОДГОТОВКА ИЗОБРАЖЕНИЯ ==================

def prepare_reference_image(image_bytes: bytes, target_size: int = 512) -> bytes:
    """
    Подготавливает референсное изображение для отправки в очередь:
    - Масштабирует с сохранением пропорций, чтобы большая сторона стала target_size
    - Добавляет чёрные полосы (padding) до квадрата target_size x target_size
    - Сжимает JPEG с качеством 85
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ratio = target_size / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        new_img = Image.new("RGB", (target_size, target_size), (0, 0, 0))
        left = (target_size - new_size[0]) // 2
        top = (target_size - new_size[1]) // 2
        new_img.paste(img, (left, top))

        output = io.BytesIO()
        new_img.save(output, format="JPEG", quality=85, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Image preparation error: {e}")
        return image_bytes

# ================== УНИВЕРСАЛЬНАЯ ОТПРАВКА ЗАДАЧИ ==================

async def send_task(
    prompt: str,
    callback_url: str,
    reference_image: Optional[bytes] = None,
    model: Optional[str] = None,
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    guidance: float = 7.5,
    strength: float = 0.7,
    negative_prompt: str = ""
) -> Optional[str]:
    """
    Отправляет задачу в Cloudflare Worker и возвращает jobId.
    """
    ref_b64 = None
    if reference_image:
        prepared = prepare_reference_image(reference_image, target_size=512)
        ref_b64 = base64.b64encode(prepared).decode()
        logger.info(f"📦 Размер base64 изображения: {len(ref_b64)} байт")

    payload = {
        "prompt": prompt,
        "reference_image_b64": ref_b64,   # только один формат – base64
        "callback_url": callback_url,
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": guidance,
        "strength": strength,
        "negative_prompt": negative_prompt
    }
    if model:
        payload["model"] = model  # для AIMage передаём FLUX

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(CF_WORKER_URL, json=payload) as resp:
                if resp.status == 202:
                    data = await resp.json()
                    job_id = data.get("jobId")
                    if job_id:
                        logger.info(f"✅ Task queued with jobId: {job_id}")
                        return job_id
                    else:
                        logger.error(f"❌ No jobId in response: {data}")
                        return None
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ Worker error {resp.status}: {error_text}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception sending task: {e}")
        return None

# ================== СПЕЦИАЛИЗИРОВАННЫЕ ФУНКЦИИ ДЛЯ РЕЖИМОВ ==================

async def generate_photoshoot(
    prompt: str,
    reference_image: bytes,
    callback_url: str,
    width: int = 768,          # для вертикального формата 4:3
    height: int = 1024,
    steps: int = 20,
    guidance: float = 7.5,
    strength: float = 0.7,
    negative_prompt: str = ""
) -> Optional[str]:
    """
    Режим AI Photoshoot (фотореализм).
    Использует stable-diffusion-v1-5-img2img.
    Параметры width/height должны соответствовать выбранному формату (из main.py).
    """
    return await send_task(
        prompt=prompt,
        reference_image=reference_image,
        callback_url=callback_url,
        model=MODEL_SD_V1_5_IMG2IMG,
        width=width,
        height=height,
        steps=steps,
        guidance=guidance,
        strength=strength,
        negative_prompt=negative_prompt
    )

async def generate_style(
    prompt: str,
    reference_image: bytes,
    callback_url: str,
    width: int = 1024,          # для AI Styles обычно 16:9
    height: int = 576,
    steps: int = 20,
    guidance: float = 7.5,
    strength: float = 0.85,     # чуть выше для стилизации
    negative_prompt: str = ""    # для стилей обычно пустой
) -> Optional[str]:
    """
    Режим AI Styles (различные стили).
    Использует ту же модель, но с другими настройками по умолчанию.
    """
    return await send_task(
        prompt=prompt,
        reference_image=reference_image,
        callback_url=callback_url,
        model=MODEL_SD_V1_5_IMG2IMG,
        width=width,
        height=height,
        steps=steps,
        guidance=guidance,
        strength=strength,
        negative_prompt=negative_prompt
    )

async def generate_ai_image(
    prompt: str,
    callback_url: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance: float = 3.5
) -> Optional[str]:
    """
    Режим AIMage (генерация без референса).
    Использует FLUX.1-schnell.
    """
    return await send_task(
        prompt=prompt,
        reference_image=None,
        callback_url=callback_url,
        model=MODEL_FLUX_SCHNELL,
        width=width,
        height=height,
        steps=steps,
        guidance=guidance,
        strength=1.0,        # не используется FLUX, но оставим
        negative_prompt=""
    )
