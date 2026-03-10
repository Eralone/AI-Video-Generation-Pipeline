from __future__ import annotations

from sqlalchemy import Boolean, Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Background(Base):
    __tablename__ = "background"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    url_page: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

