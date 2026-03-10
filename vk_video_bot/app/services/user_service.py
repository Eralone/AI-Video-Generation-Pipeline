from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..utils.exceptions import UserNotAuthorizedError, UserNotFoundError


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check_authorization(self, vk_user_id: int) -> bool:
        stmt = select(User).where(User.vk_user_id == vk_user_id)
        result = await self._session.execute(stmt)
        user: User | None = result.scalar_one_or_none()
        if not user:
            return False
        return bool(user.is_authorized)

    async def get_or_create(self, vk_user_id: int) -> Tuple[User, bool]:
        stmt = select(User).where(User.vk_user_id == vk_user_id)
        result = await self._session.execute(stmt)
        user: User | None = result.scalar_one_or_none()
        if user:
            return user, False

        now = datetime.now(timezone.utc)
        user = User(
            vk_user_id=vk_user_id,
            is_authorized=False,
            created_at=now,
            updated_at=None,
        )
        self._session.add(user)
        await self._session.flush()
        return user, True

    async def authorize_user(self, vk_user_id: int) -> User:
        stmt = select(User).where(User.vk_user_id == vk_user_id)
        result = await self._session.execute(stmt)
        user: User | None = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError(f"User with vk_user_id={vk_user_id} not found")
        user.is_authorized = True
        user.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return user

    async def get_by_vk_id(self, vk_user_id: int) -> User | None:
        stmt = select(User).where(User.vk_user_id == vk_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

