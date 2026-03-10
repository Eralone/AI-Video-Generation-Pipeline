from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import User


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    background_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("background.id"), nullable=True
    )
    avatar_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("avatar.id"), nullable=True
    )
    voice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("voice.id"), nullable=True
    )

    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship("User", lazy="joined")

