import httpx
import logging
from typing import Optional
from config import FACEFUSION_URL

logger = logging.getLogger(__name__)

class FaceFusionClient:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or FACEFUSION_URL
        if not self.api_url:
            raise ValueError("FACEFUSION_URL не задан")

    async def swap_face(self, source_face_bytes: bytes, target_image_bytes: bytes) -> Optional[bytes]:
        """
        Отправляет два изображения на HF Space и возвращает результат замены лица.
        Ожидается, что эндпоинт /swap принимает multipart/form-data с полями:
          - source: файл с лицом
          - target: файл с целевым изображением
        Возвращает изображение в теле ответа.
        """
        url = f"{self.api_url}/swap"
        files = {
            "source": ("face.jpg", source_face_bytes, "image/jpeg"),
            "target": ("target.jpg", target_image_bytes, "image/jpeg")
        }
        logger.info(f"🔄 Отправка запроса на FaceFusion API: {url}")
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, files=files)
            resp.raise_for_status()
            return resp.content
