from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Tuple

import httpx
import structlog
import asyncio

from ..config import settings
from ..utils.types import GenerationStatus


logger = structlog.get_logger(__name__)


class Veo3Service:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.base_url = "https://veo.googleapis.com"

    async def _with_retry(self, func, *args, **kwargs):
        delay = 1.0
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPError as exc:
                logger.warning("veo3_http_error", attempt=attempt + 1, error=str(exc))
                if attempt == 2:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def generate_video(self, video_prompt: str, audio_path: str, job_id: str) -> str:
        async def _do_request() -> str:
            url = f"{self.base_url}/v1/videos:generate"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            audio_uri = f"file://{audio_path}"
            payload = {
                "prompt": video_prompt,
                "audio_uri": audio_uri,
                "aspectRatio": "9:16",
                "durationSeconds": 120,
            }
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                operation_name = data.get("name")
                logger.info("veo3_generate_video", operation=operation_name)
                return operation_name

        return await self._with_retry(_do_request)

    async def poll_status(self, generation_id: str) -> Tuple[GenerationStatus, str | None]:
        """
        Опрос операции Veo3 до 20 минут.
        Возвращает (status, video_url|None).
        """
        url = f"{self.base_url}/v1/operations/{generation_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            for _ in range(120):  # up to 20 minutes (every 10s)
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                if data.get("done"):
                    response = data.get("response") or {}
                    video = response.get("video") or {}
                    video_url = video.get("uri")
                    logger.info("veo3_operation_done", operation=generation_id, video_url=video_url)
                    return "done", video_url
                await asyncio.sleep(10)
        logger.warning("veo3_operation_timeout", operation=generation_id)
        return "error", None

    async def download_video(self, video_url: str, job_id: str) -> str:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            video_dir = settings.VIDEO_STORAGE_PATH
            Path(video_dir).mkdir(parents=True, exist_ok=True)
            path = Path(video_dir) / f"{job_id}.mp4"
            path.write_bytes(resp.content)
            logger.info("veo3_download_video", path=str(path))
            return str(path)

    async def generate_and_upload(self, video_prompt: str, audio_path: str, job_id: str) -> str:
        generation_id = await self.generate_video(video_prompt, audio_path, job_id)
        status, video_url = await self.poll_status(generation_id)
        if status != "done" or not video_url:
            raise RuntimeError("Video generation failed or timed out")
        return await self.download_video(video_url, job_id)

