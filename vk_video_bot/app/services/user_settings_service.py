from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user_settings import UserSettings


class UserSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_or_create(self, user_id: int) -> UserSettings:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await self._session.execute(stmt)
        settings: UserSettings | None = result.scalar_one_or_none()
        if settings:
            return settings
        settings = UserSettings(
            user_id=user_id,
            background_id=None,
            avatar_id=None,
            voice_id=None,
            topic=None,
            keywords=None,
            description=None,
            updated_at=datetime.now(timezone.utc),
        )
        self._session.add(settings)
        await self._session.flush()
        return settings

    async def get_settings(self, user_id: int) -> UserSettings:
        return await self._get_or_create(user_id)

    async def set_topic(self, user_id: int, topic: str) -> UserSettings:
        settings = await self._get_or_create(user_id)
        settings.topic = topic
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return settings

    async def set_keywords(self, user_id: int, keywords: str) -> UserSettings:
        settings = await self._get_or_create(user_id)
        settings.keywords = keywords
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return settings

    async def set_description(self, user_id: int, description: str) -> UserSettings:
        settings = await self._get_or_create(user_id)
        settings.description = description
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return settings

    async def set_background(self, user_id: int, background_id: int) -> UserSettings:
        settings = await self._get_or_create(user_id)
        settings.background_id = background_id
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return settings

    async def set_avatar(self, user_id: int, avatar_id: int) -> UserSettings:
        settings = await self._get_or_create(user_id)
        settings.avatar_id = avatar_id
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return settings

    async def set_voice(self, user_id: int, voice_id: int) -> UserSettings:
        settings = await self._get_or_create(user_id)
        settings.voice_id = voice_id
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return settings

    async def validate_required_fields(self, user_id: int) -> Tuple[bool, list[str]]:
        settings = await self._get_or_create(user_id)
        missing: list[str] = []
        if not settings.topic:
            missing.append("topic")
        if not settings.background_id:
            missing.append("background_id")
        if not settings.avatar_id:
            missing.append("avatar_id")
        if not settings.voice_id:
            missing.append("voice_id")
        return not missing, missing

    async def clear_generation_data(self, user_id: int) -> None:
        settings = await self._get_or_create(user_id)
        settings.topic = None
        settings.keywords = None
        settings.description = None
        settings.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

