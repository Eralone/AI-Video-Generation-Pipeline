from __future__ import annotations

from typing import Iterable, List

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.avatar import Avatar
from ..models.background import Background
from ..models.voice import Voice
from ..utils.keyboards import build_selection_keyboard


class CatalogService:
    def __init__(self, session: AsyncSession, redis: Redis, ttl_seconds: int = 300) -> None:
        self._session = session
        self._redis = redis
        self._ttl = ttl_seconds

    async def _get_cached(self, key: str) -> list[dict] | None:
        raw = await self._redis.get(key)
        if not raw:
            return None
        from json import loads

        return loads(raw)

    async def _set_cached(self, key: str, value: list[dict]) -> None:
        from json import dumps

        await self._redis.set(key, dumps(value), ex=self._ttl)

    async def get_backgrounds(self) -> list[Background]:
        key = "catalog:background"
        cached = await self._get_cached(key)
        if cached is not None:
            return [Background(**item) for item in cached]
        stmt = select(Background).where(Background.is_active.is_(True))
        result = await self._session.execute(stmt)
        items: List[Background] = list(result.scalars().all())
        await self._set_cached(key, [self._serialize_background(b) for b in items])
        return items

    async def get_avatars(self) -> list[Avatar]:
        key = "catalog:avatar"
        cached = await self._get_cached(key)
        if cached is not None:
            return [Avatar(**item) for item in cached]
        stmt = select(Avatar).where(Avatar.is_active.is_(True))
        result = await self._session.execute(stmt)
        items: List[Avatar] = list(result.scalars().all())
        await self._set_cached(key, [self._serialize_avatar(a) for a in items])
        return items

    async def get_voices(self) -> list[Voice]:
        key = "catalog:voice"
        cached = await self._get_cached(key)
        if cached is not None:
            return [Voice(**item) for item in cached]
        stmt = select(Voice).where(Voice.is_active.is_(True))
        result = await self._session.execute(stmt)
        items: List[Voice] = list(result.scalars().all())
        await self._set_cached(key, [self._serialize_voice(v) for v in items])
        return items

    async def get_background_by_id(self, background_id: int) -> Background | None:
        stmt = select(Background).where(Background.id == background_id, Background.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_avatar_by_id(self, avatar_id: int) -> Avatar | None:
        stmt = select(Avatar).where(Avatar.id == avatar_id, Avatar.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_voice_by_id(self, voice_id: int) -> Voice | None:
        stmt = select(Voice).where(Voice.id == voice_id, Voice.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def build_selection_keyboard(self, items: Iterable[Background | Avatar | Voice], callback_prefix: str) -> dict:
        pairs = [(item.id, item.name) for item in items]
        return build_selection_keyboard(pairs, callback_prefix)

    @staticmethod
    def _serialize_background(bg: Background) -> dict:
        return {
            "id": bg.id,
            "name": bg.name,
            "prompt": bg.prompt,
            "url_page": bg.url_page,
            "is_active": bg.is_active,
        }

    @staticmethod
    def _serialize_avatar(av: Avatar) -> dict:
        return {
            "id": av.id,
            "name": av.name,
            "prompt": av.prompt,
            "url_page": av.url_page,
            "is_active": av.is_active,
        }

    @staticmethod
    def _serialize_voice(vc: Voice) -> dict:
        return {
            "id": vc.id,
            "name": vc.name,
            "prompt": vc.prompt,
            "url_voice": vc.url_voice,
            "is_active": vc.is_active,
        }

