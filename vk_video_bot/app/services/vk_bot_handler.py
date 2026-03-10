from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from ..config import settings
from ..db.session import async_session_factory
from ..models.generation_job import GenerationJob
from ..services.catalog_service import CatalogService
from ..services.user_service import UserService
from ..services.user_settings_service import UserSettingsService
from ..tasks.generate_video import generate_video_task
from ..utils.exceptions import UserNotAuthorizedError
from ..utils.keyboards import build_keyboard, build_text_button


logger = structlog.get_logger(__name__)


class VKBotHandler:
    API_URL = "https://api.vk.com/method"
    API_VERSION = "5.199"

    def __init__(self) -> None:
        self.token = settings.VK_TOKEN

    async def send_message(self, user_id: int, text: str, keyboard: dict | None = None) -> None:
        payload: dict[str, Any] = {
            "user_id": user_id,
            "random_id": int(time.time() * 1000),
            "message": text,
            "v": self.API_VERSION,
            "access_token": self.token,
        }
        if keyboard is not None:
            import json

            payload["keyboard"] = json.dumps(keyboard, ensure_ascii=False)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{self.API_URL}/messages.send", data=payload)
            resp.raise_for_status()
            logger.info("vk_send_message", user_id=user_id)

    async def send_result_to_user(self, user_id: int, share_links, pub_text) -> None:
        keyboard = build_keyboard(
            [
                [
                    build_text_button("Смотреть", {"url": share_links.watch_url}),
                    build_text_button("Скачать", {"url": share_links.download_url}),
                ]
            ],
            inline=True,
        )
        text = f"{pub_text.title}\n\n{pub_text.description}"
        await self.send_message(user_id, text, keyboard)

    async def handle_message(self, event: dict) -> None:
        message = event.get("object", {}).get("message", {})
        user_id = message.get("from_id")
        text: str = (message.get("text") or "").strip()
        start_ts = time.monotonic()

        if not user_id:
            return

        # Обработка callback-пейлоада от кнопок
        payload = message.get("payload")
        if isinstance(payload, dict) and "data" in payload:
            data = payload.get("data") or ""
            await self._handle_selection(user_id, str(data))
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            logger.info("vk_callback_handled", user_id=user_id, data=data, duration_ms=duration_ms)
            return

        command, *rest = text.split(" ", 1)
        arg = rest[0] if rest else ""

        try:
            if command == "/start":
                await self.cmd_start(user_id)
            elif command == "/topic":
                await self.cmd_topic(user_id, arg)
            elif command == "/important":
                await self.cmd_important(user_id, arg)
            elif command == "/text":
                await self.cmd_text(user_id, arg)
            elif command == "/background":
                await self.cmd_background(user_id)
            elif command == "/avatar":
                await self.cmd_avatar(user_id)
            elif command == "/voice":
                await self.cmd_voice(user_id)
            elif command == "/generate":
                await self.cmd_generate(user_id)
            else:
                await self.send_message(user_id, "Неизвестная команда. Используйте /start.")
        finally:
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            logger.info("vk_command_handled", user_id=user_id, command=command, duration_ms=duration_ms)

    async def _ensure_authorized(self, user_id: int) -> None:
        async with async_session_factory() as session:
            user_service = UserService(session)
            is_auth = await user_service.check_authorization(user_id)
            if not is_auth:
                keyboard = build_keyboard(
                    [
                        [
                            build_text_button(
                                "Авторизоваться",
                                {"url": "https://oauth.vk.com/authorize"},  # TODO: реальная ссылка OAuth
                            )
                        ]
                    ],
                    inline=False,
                )
                await self.send_message(user_id, "Для продолжения необходимо авторизоваться.", keyboard)
                raise UserNotAuthorizedError

    async def cmd_start(self, user_id: int) -> None:
        async with async_session_factory() as session:
            user_service = UserService(session)
            user, is_new = await user_service.get_or_create(user_id)
            if not user.is_authorized:
                keyboard = build_keyboard(
                    [
                        [
                            build_text_button(
                                "Авторизоваться",
                                {"url": "https://oauth.vk.com/authorize"},
                            )
                        ]
                    ],
                    inline=False,
                )
                await self.send_message(user_id, "Привет! Для начала работы авторизуйтесь.", keyboard)
            else:
                await self.send_message(user_id, "Вы уже авторизованы. Используйте /topic для задания темы.")

    async def cmd_topic(self, user_id: int, text: str) -> None:
        await self._ensure_authorized(user_id)
        async with async_session_factory() as session:
            user_service = UserService(session)
            user = await user_service.get_by_vk_id(user_id)
            if not user:
                return
            settings_service = UserSettingsService(session)
            await settings_service.set_topic(user.id, text)
            await session.commit()
        await self.send_message(user_id, "Тема сохранена.")

    async def cmd_important(self, user_id: int, text: str) -> None:
        await self._ensure_authorized(user_id)
        async with async_session_factory() as session:
            user_service = UserService(session)
            user = await user_service.get_by_vk_id(user_id)
            if not user:
                return
            settings_service = UserSettingsService(session)
            await settings_service.set_keywords(user.id, text)
            await session.commit()
        await self.send_message(user_id, "Ключевые слова сохранены.")

    async def cmd_text(self, user_id: int, text: str) -> None:
        await self._ensure_authorized(user_id)
        async with async_session_factory() as session:
            user_service = UserService(session)
            user = await user_service.get_by_vk_id(user_id)
            if not user:
                return
            settings_service = UserSettingsService(session)
            await settings_service.set_description(user.id, text)
            await session.commit()
        await self.send_message(user_id, "Описание сохранено.")

    async def cmd_background(self, user_id: int) -> None:
        await self._ensure_authorized(user_id)
        from redis.asyncio import Redis

        async with async_session_factory() as session:
            redis = Redis.from_url(settings.CELERY_BROKER_URL)
            catalog = CatalogService(session, redis)
            backgrounds = await catalog.get_backgrounds()
            keyboard = catalog.build_selection_keyboard(backgrounds, "select_bg")
        await self.send_message(user_id, "Выберите фон:", keyboard)

    async def cmd_avatar(self, user_id: int) -> None:
        await self._ensure_authorized(user_id)
        from redis.asyncio import Redis

        async with async_session_factory() as session:
            redis = Redis.from_url(settings.CELERY_BROKER_URL)
            catalog = CatalogService(session, redis)
            avatars = await catalog.get_avatars()
            keyboard = catalog.build_selection_keyboard(avatars, "select_avatar")
        await self.send_message(user_id, "Выберите аватар:", keyboard)

    async def cmd_voice(self, user_id: int) -> None:
        await self._ensure_authorized(user_id)
        from redis.asyncio import Redis

        async with async_session_factory() as session:
            redis = Redis.from_url(settings.CELERY_BROKER_URL)
            catalog = CatalogService(session, redis)
            voices = await catalog.get_voices()
            keyboard = catalog.build_selection_keyboard(voices, "select_voice")
        await self.send_message(user_id, "Выберите голос:", keyboard)

    async def cmd_generate(self, user_id: int) -> None:
        await self._ensure_authorized(user_id)
        async with async_session_factory() as session:
            user_service = UserService(session)
            user = await user_service.get_by_vk_id(user_id)
            if not user:
                return
            settings_service = UserSettingsService(session)
            is_valid, missing = await settings_service.validate_required_fields(user.id)
            if not is_valid:
                await self.send_message(
                    user_id,
                    f"Не заполнены обязательные поля: {', '.join(missing)}. "
                    "Укажите тему, фон, аватар и голос.",
                )
                return

            job = GenerationJob(user_id=user.id, status="pending")
            session.add(job)
            await session.commit()

        generate_video_task.delay(str(job.id), user.id)
        await self.send_message(user_id, "Задача на генерацию видео создана. Это может занять до 20 минут.")

    async def _handle_selection(self, user_id: int, data: str) -> None:
        """
        Обработка callback-кнопок вида:
        select_bg:{id}, select_avatar:{id}, select_voice:{id}
        """
        try:
            prefix, raw_id = data.split(":", 1)
            item_id = int(raw_id)
        except ValueError:
            await self.send_message(user_id, "Некорректный выбор.")
            return

        await self._ensure_authorized(user_id)

        from redis.asyncio import Redis

        async with async_session_factory() as session:
            user_service = UserService(session)
            user = await user_service.get_by_vk_id(user_id)
            if not user:
                return

            settings_service = UserSettingsService(session)
            redis = Redis.from_url(settings.CELERY_BROKER_URL)
            catalog = CatalogService(session, redis)

            if prefix == "select_bg":
                bg = await catalog.get_background_by_id(item_id)
                if not bg:
                    await self.send_message(user_id, "Фон не найден.")
                    return
                await settings_service.set_background(user.id, bg.id)
                await session.commit()
                await self.send_message(user_id, f"Фон «{bg.name}» выбран.")
            elif prefix == "select_avatar":
                av = await catalog.get_avatar_by_id(item_id)
                if not av:
                    await self.send_message(user_id, "Аватар не найден.")
                    return
                await settings_service.set_avatar(user.id, av.id)
                await session.commit()
                await self.send_message(user_id, f"Аватар «{av.name}» выбран.")
            elif prefix == "select_voice":
                vc = await catalog.get_voice_by_id(item_id)
                if not vc:
                    await self.send_message(user_id, "Голос не найден.")
                    return
                await settings_service.set_voice(user.id, vc.id)
                await session.commit()
                await self.send_message(user_id, f"Голос «{vc.name}» выбран.")
            else:
                await self.send_message(user_id, "Неизвестный тип кнопки.")

