from __future__ import annotations

from pathlib import Path
import asyncio

import httpx
from mutagen.mp3 import MP3
import structlog

from ..config import settings


logger = structlog.get_logger(__name__)


class VoiSparkService:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url or str(settings.VOISPARK_API_URL)
        self.api_key = api_key or settings.VOISPARK_API_KEY

    async def _with_retry(self, func, *args, **kwargs):
        delay = 1.0
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPError as exc:
                logger.warning("voispark_http_error", attempt=attempt + 1, error=str(exc))
                if attempt == 2:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def generate_audio(self, script: str, audio_prompt: str) -> bytes:
        async def _do_request() -> bytes:
            url = f"{self.base_url.rstrip('/')}/v1/tts"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "text": script,
                "voice_prompt": audio_prompt,
                "max_duration_seconds": 120,
                "format": "mp3",
            }
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                logger.info("voispark_generate_audio", status_code=resp.status_code)
                return resp.content

        return await self._with_retry(_do_request)

    async def save_audio(self, audio_bytes: bytes, job_id: str) -> str:
        audio_dir = settings.AUDIO_STORAGE_PATH
        Path(audio_dir).mkdir(parents=True, exist_ok=True)
        path = Path(audio_dir) / f"{job_id}.mp3"
        path.write_bytes(audio_bytes)
        logger.info("voispark_save_audio", path=str(path))
        return str(path)

    async def get_audio_duration(self, audio_bytes: bytes) -> float:
        # save to temp file to inspect duration
        tmp_path = Path(settings.AUDIO_STORAGE_PATH) / "_tmp_duration.mp3"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(audio_bytes)
        audio = MP3(tmp_path)
        duration = float(audio.info.length)
        tmp_path.unlink(missing_ok=True)
        return duration

    async def generate_and_save(self, script: str, audio_prompt: str, job_id: str) -> str:
        audio_bytes = await self.generate_audio(script, audio_prompt)
        return await self.save_audio(audio_bytes, job_id)

