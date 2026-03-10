from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class PublicationText:
    title: str
    description: str
    tags: list[str]


@dataclass(slots=True)
class ShareLinks:
    watch_url: str
    download_url: str
    embed_url: str | None = None


GenerationStatus = Literal["pending", "processing", "done", "error"]

