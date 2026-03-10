from __future__ import annotations

import asyncio
from typing import Any, Literal

import structlog
from openai import AsyncOpenAI

from ..config import settings
from ..utils.types import PublicationText


logger = structlog.get_logger(__name__)


class AITextService:
    def __init__(self, provider: Literal["openai", "gigachat"] | None = None) -> None:
        self.provider = provider or settings.AI_PROVIDER
        self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if self.provider == "openai" else None

    async def _with_retry(self, func, *args, **kwargs):
        delay = 1.0
        for attempt in range(3):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ai_request_failed", attempt=attempt + 1, error=str(exc))
                if attempt == 2:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def generate_audio_script(
        self,
        topic: str,
        avatar_prompt: str,
        keywords: str | None = None,
        description: str | None = None,
    ) -> str:
        async def _call_openai() -> str:
            assert self._openai_client is not None
            system_prompt = (
                "Ты - профессиональный сценарист коротких видеороликов для социальной сети VK.\n"
                "Твоя задача: написать живой, разговорный текст для озвучки видеоклипа.\n"
                "Требования: не более 150 слов, разговорный стиль, зацепка -> основная мысль -> вывод.\n"
                "Если переданы ключевые слова - вставь их ТОЧНО в текст.\n"
                "Если передано описание - переформулируй его под контекст.\n"
                "Учитывай аватара и его описание.\n"
                "Верни только текст без пояснений."
            )
            user_content = (
                f"Тема: {topic}\n"
                f"Аватар: {avatar_prompt}\n"
                f"Ключевые слова: {keywords or ''}\n"
                f"Описание: {description or ''}"
            )
            resp = await self._openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=400,
                temperature=0.75,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            content = resp.choices[0].message.content or ""
            logger.info(
                "ai_generate_audio_script",
                model=resp.model,
                prompt_tokens=resp.usage.prompt_tokens if resp.usage else None,
                completion_tokens=resp.usage.completion_tokens if resp.usage else None,
            )
            return content.strip()

        if self.provider == "openai":
            return await self._with_retry(_call_openai)
        raise NotImplementedError("GigaChat provider is not implemented yet")

    async def generate_publication_text(self, topic: str, script: str) -> PublicationText:
        async def _call_openai() -> PublicationText:
            assert self._openai_client is not None
            system_prompt = (
                "Ты - SMM-специалист по контенту для ВКонтакте.\n"
                "На основе темы и аудио-скрипта создай текст для публикации.\n"
                "Верни строго JSON с полями title, description, tags."
            )
            user_content = f"Тема: {topic}\nАудио-скрипт: {script}"
            resp = await self._openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=400,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
            logger.info(
                "ai_generate_publication_text",
                model=resp.model,
                prompt_tokens=resp.usage.prompt_tokens if resp.usage else None,
                completion_tokens=resp.usage.completion_tokens if resp.usage else None,
            )
            import json

            data: dict[str, Any] = json.loads(raw)
            return PublicationText(
                title=data.get("title", "")[:100],
                description=data.get("description", "")[:500],
                tags=list(map(str, data.get("tags", [])))[:15],
            )

        if self.provider == "openai":
            return await self._with_retry(_call_openai)
        raise NotImplementedError("GigaChat provider is not implemented yet")

    async def generate_video_prompt(self, avatar_prompt: str, background_prompt: str) -> str:
        async def _call_openai() -> str:
            assert self._openai_client is not None
            system_prompt = (
                "Ты - специалист по генерации видео через нейросети.\n"
                "Объедини промт аватара и фона в единый промт для Veo 3.\n"
                "Добавь технические параметры: 1080x1920, 9:16, max 2 минуты, high-quality anime style.\n"
                "Верни только текст промта на английском языке."
            )
            user_content = f"Промт аватара: {avatar_prompt}\nПромт фона: {background_prompt}"
            resp = await self._openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=400,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            content = resp.choices[0].message.content or ""
            logger.info("ai_generate_video_prompt", model=resp.model)
            return content.strip()

        if self.provider == "openai":
            return await self._with_retry(_call_openai)
        raise NotImplementedError("GigaChat provider is not implemented yet")

    async def generate_audio_prompt(self, audio_script: str, voice_prompt: str) -> str:
        async def _call_openai() -> str:
            assert self._openai_client is not None
            system_prompt = (
                "Создай контекстный промт для TTS-системы VoiSpark.\n"
                "Опиши голос (пол, возраст, тембр), стиль подачи, разговорный формат и естественные паузы.\n"
                "Верни только текст промта."
            )
            user_content = f"Описание голоса: {voice_prompt}\nТекст для озвучки: {audio_script}"
            resp = await self._openai_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=400,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            content = resp.choices[0].message.content or ""
            logger.info("ai_generate_audio_prompt", model=resp.model)
            return content.strip()

        if self.provider == "openai":
            return await self._with_retry(_call_openai)
        raise NotImplementedError("GigaChat provider is not implemented yet")

