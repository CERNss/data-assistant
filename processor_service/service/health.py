from __future__ import annotations

import asyncio

from aiohttp import web
from loguru import logger

HEALTH_HOST = "0.0.0.0"
HEALTH_PORT = 8080


async def _health_handler(_request: web.Request) -> web.Response:
    from .chat_image.tagger_worker import worker_is_healthy

    if worker_is_healthy():
        return web.json_response({"status": "ok"})
    return web.json_response(
        {"status": "unhealthy", "reason": "nats_disconnected"},
        status=503,
    )


async def run_health_server(
    host: str = HEALTH_HOST,
    port: int = HEALTH_PORT,
    stop_event: asyncio.Event | None = None,
) -> None:
    app = web.Application()
    app.router.add_route("GET", "/health", _health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Health server listening: host={} port={}", host, port)
    try:
        if stop_event is None:
            await asyncio.Future()
        else:
            await stop_event.wait()
    finally:
        await runner.cleanup()
