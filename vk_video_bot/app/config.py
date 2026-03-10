from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    AI_PROVIDER: Literal["openai", "gigachat"] = "openai"

    OPENAI_API_KEY: str | None = None
    GIGACHAT_API_KEY: str | None = None

    VOISPARK_API_KEY: str
    VOISPARK_API_URL: AnyUrl = Field(default="https://api.voispark.com")

    GOOGLE_API_KEY: str | None = None
    VEO3_SERVICE_ACCOUNT_JSON_PATH: Path | None = None

    KINESCOPE_API_KEY: str

    VK_TOKEN: str
    VK_SECRET_KEY: str

    DATABASE_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str | None = None

    AUDIO_STORAGE_PATH: Path = Path("/data/audio")
    VIDEO_STORAGE_PATH: Path = Path("/data/video")

    SENTRY_DSN: str | None = None
    LOG_LEVEL: str = "INFO"

    INTERNAL_API_TOKEN: str = "internal-token"


settings = Settings()  # type: ignore[arg-type]

