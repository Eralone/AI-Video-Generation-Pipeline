from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import structlog

from ..config import settings
from ..utils.types import PublicationText, ShareLinks


logger = structlog.get_logger(__name__)


class KinescopeService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.KINESCOPE_API_KEY
        self.base_url = "https://api.kinescope.io/v1"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _with_retry(self, func, *args, **kwargs):
        delay = 5.0
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as exc:
                if 500 <= exc.response.status_code < 600 and attempt < 2:
                    logger.warning(
                        "kinescope_http_5xx",
                        attempt=attempt + 1,
                        status_code=exc.response.status_code,
                    )
                    import asyncio

                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise

    async def upload_video(self, video_path: str, project_id: str) -> str:
        async def _do_upload() -> str:
            url = f"{self.base_url}/videos"
            path = Path(video_path)
            files = {"file": (path.name, path.read_bytes(), "video/mp4")}
            data = {"project_id": project_id}
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(url, headers=self._headers(), data=data, files=files)
                resp.raise_for_status()
                body: dict[str, Any] = resp.json()
                vid = body["data"]["id"]
                logger.info("kinescope_upload_video", video_id=vid)
                return vid

        return await self._with_retry(_do_upload)

    async def set_metadata(self, video_id: str, pub_text: PublicationText) -> None:
        async def _do_patch() -> None:
            url = f"{self.base_url}/videos/{video_id}"
            payload = {
                "title": pub_text.title,
                "description": pub_text.description,
                "tags": pub_text.tags,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.patch(url, json=payload, headers=self._headers())
                resp.raise_for_status()
                logger.info("kinescope_set_metadata", video_id=video_id)

        await self._with_retry(_do_patch)

    async def get_share_links(self, video_id: str) -> ShareLinks:
        url = f"{self.base_url}/videos/{video_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            body: dict[str, Any] = resp.json()
            data = body["data"]
            watch_url = data.get("share_link") or ""
            download_url = data.get("download_link") or ""
            embed_url = data.get("embed_link")
            logger.info("kinescope_get_share_links", video_id=video_id)
            return ShareLinks(watch_url=watch_url, download_url=download_url, embed_url=embed_url)

    async def publish_video(self, video_path: str, pub_text: PublicationText, project_id: str) -> ShareLinks:
        video_id = await self.upload_video(video_path, project_id)
        await self.set_metadata(video_id, pub_text)
        return await self.get_share_links(video_id)

