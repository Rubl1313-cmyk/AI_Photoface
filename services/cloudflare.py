import httpx
import logging
from config import CF_WORKER_URL, CF_API_KEY

logger = logging.getLogger(__name__)

async def generate_with_cloudflare(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4
) -> bytes:
    """Генерация через Cloudflare Worker"""
    async with httpx.AsyncClient(timeout=90.0) as client:
        data = {
            "prompt": prompt,
            "width": str(width),
            "height": str(height),
            "steps": str(steps),
        }
        response = await client.post(
            CF_WORKER_URL.strip(),
            headers={"Authorization": f"Bearer {CF_API_KEY}"},
            data=data,
            timeout=90
        )
        response.raise_for_status()
        if len(response.content) < 1000:
            raise ValueError("Пустой ответ от генератора")
        logger.info(f"✅ Cloudflare: {len(response.content)} bytes")
        return response.content