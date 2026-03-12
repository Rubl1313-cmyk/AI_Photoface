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

# Конфигурации моделей
MODEL_SDXL = "@cf/stabilityai/stable-diffusion-xl-base-1.0"      # максимальное качество
MODEL_FLUX_SCHNELL = "@cf/black-forest-labs/flux-1-schnell"      # быстрая, без референса

# ================== ПОДГОТОВКА ИЗОБРАЖЕНИЯ ==================

def prepare_reference_image(image_bytes: bytes, target_size: int = 1024) -> bytes:
    """
    Подготавливает референсное изображение:
    - Масштабирует с сохранением пропорций, чтобы большая сторона стала target_size
    - Добавляет чёрные полосы (padding) до квадрата target_size x target_size
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
        new_img.save(output, format="JPEG", quality=95, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"❌ Image preparation error: {e}")
        return image_bytes

# ================== УНИВЕРСАЛЬНАЯ ОТПРАВКА ЗАДАЧИ ==================

async def send_task(
    prompt: str,
    callback_url: str,
    reference_image: Optional[bytes] = None,
    model: str = MODEL_SDXL,
    width: int = 1024,
    height: int = 1024,
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
        prepared = prepare_reference_image(reference_image, target_size=1024)
        ref_b64 = base64.b64encode(prepared).decode()

    payload = {
        "prompt": prompt,
        "reference_image": ref_b64,
        "callback_url": callback_url,
        "model": model,
        "width": min(1024, width),
        "height": min(1024, height),
        "steps": steps,
        "guidance": guidance,
        "strength": strength,
        "negative_prompt": negative_prompt
    }

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

# ================== СПЕЦИАЛИЗИРОВАННЫЕ ФУНКЦИИ ==================

async def generate_photoshoot(
    prompt: str,
    reference_image: bytes,
    callback_url: str,
    width: int = 1024,
    height: int = 1024,
    negative_prompt: str = "",
    strength: float = 0.7
) -> Optional[str]:
    """AI Photoshoot: максимальный фотореализм через SDXL"""
    return await send_task(
        prompt=prompt,
        reference_image=reference_image,
        callback_url=callback_url,
        model=MODEL_SDXL,
        width=width,
        height=height,
        steps=20,
        guidance=7.5,
        strength=strength,
        negative_prompt=negative_prompt
    )

async def generate_style(
    prompt: str,
    reference_image: bytes,
    callback_url: str,
    width: int = 1024,
    height: int = 1024,
    strength: float = 0.85,
    negative_prompt: str = ""
) -> Optional[str]:
    """AI Styles: стилизация через SDXL (можно заменить на Dreamshaper)"""
    return await send_task(
        prompt=prompt,
        reference_image=reference_image,
        callback_url=callback_url,
        model=MODEL_SDXL,  # при желании заменить на MODEL_DREAMSHAPER
        width=width,
        height=height,
        steps=20,
        guidance=7.5,
        strength=strength,
        negative_prompt=negative_prompt
    )

async def generate_ai_image(
    prompt: str,
    callback_url: str,
    width: int = 1024,
    height: int = 1024
) -> Optional[str]:
    """AIMage: быстрая генерация без референса через FLUX.1-schnell"""
    return await send_task(
        prompt=prompt,
        reference_image=None,
        callback_url=callback_url,
        model=MODEL_FLUX_SCHNELL,
        width=width,
        height=height,
        steps=4,          # FLUX оптимально работает при 4 шагах
        guidance=3.5,     # рекомендуемое значение для FLUX
        strength=1.0,     # не используется, но оставим
        negative_prompt=""
    )
