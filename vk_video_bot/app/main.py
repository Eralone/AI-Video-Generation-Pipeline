from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import Any

import structlog
from aiohttp import web

from .config import settings
from .services.vk_bot_handler import VKBotHandler


logger = structlog.get_logger(__name__)


def verify_signature(body: bytes, secret: str, sig: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


async def vk_callback(request: web.Request) -> web.Response:
    body = await request.read()
    signature = request.headers.get("X-VK-Signature", "")

    if not verify_signature(body, settings.VK_SECRET_KEY, signature):
        logger.warning("vk_callback_invalid_signature")
        return web.Response(status=403, text="forbidden")

    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.warning("vk_callback_invalid_json")
        return web.Response(status=400, text="bad request")

    event_type = payload.get("type")
    logger.info("vk_callback_event", event_type=event_type)

    handler: VKBotHandler = request.app["vk_bot_handler"]
    if event_type == "message_new":
        await handler.handle_message(payload)
    elif event_type == "message_event":
        # VK callback для нажатия inline-кнопок
        await handler.handle_message(payload)

    return web.json_response({"response": "ok"})


async def internal_health(request: web.Request) -> web.Response:
    token = request.headers.get("X-Internal-Token")
    if token != settings.INTERNAL_API_TOKEN:
        return web.Response(status=403, text="forbidden")
    return web.json_response({"status": "ok"})


async def create_app() -> web.Application:
    app = web.Application()
    app["vk_bot_handler"] = VKBotHandler()
    app.router.add_post("/vk/callback", vk_callback)
    app.router.add_get("/internal/health", internal_health)
    return app


def main() -> None:
    app = asyncio.run(create_app())
    web.run_app(app, port=8080)


if __name__ == "__main__":
    main()

