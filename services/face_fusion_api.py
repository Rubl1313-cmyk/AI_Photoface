# services/face_fusion_api.py
"""
🎭 FaceFusion API Client — Enhanced
"""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FaceFusionClient:
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")
        logger.info(f"🔗 FaceFusionClient initialized: {self.api_url}")
    
    async def swap_face(
        self,
        source_face_bytes: bytes,
        target_image_bytes: bytes,
        face_enhancer: bool = True
    ) -> Optional[bytes]:
        """Замена лица с улучшением качества"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                files = {
                    "target": ("target.jpg", target_image_bytes, "image/jpeg"),
                    "source": ("source.jpg", source_face_bytes, "image/jpeg")
                }
                
                data = {
                    "face_enhancer": "true" if face_enhancer else "false",
                    "face_swapper_model": "inswapper_128"
                }
                
                logger.info(f"🔄 FaceFusion request (timeout=300s)")
                
                response = await client.post(
                    f"{self.api_url}/swap",
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Face swap success: {len(response.content)} bytes")
                    return response.content
                else:
                    logger.error(f"❌ FaceFusion error {response.status_code}: {response.text[:200]}")
                    return None
        
        except httpx.TimeoutException:
            logger.error("❌ FaceFusion timeout after 300s")
            return None
        except Exception as e:
            logger.error(f"❌ Face swap error: {type(e).__name__}: {e}")
            return None
    
    async def swap_face_simple(
        self,
        source_face_bytes: bytes,
        target_image_bytes: bytes
    ) -> Optional[bytes]:
        """Простая замена лица (без дополнительных параметров)"""
        return await self.swap_face(
            source_face_bytes=source_face_bytes,
            target_image_bytes=target_image_bytes,
            face_enhancer=True
        )
