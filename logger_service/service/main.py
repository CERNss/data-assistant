from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

from loguru import logger

from . import telemetry
from .chat_image.config import load_chat_image_config
from .chat_image.nats_publisher import close_nats_publisher
from .chat_image.outbox_relay import run_outbox_relay
from .napcat.config import load_napcat_config
from .napcat.connection import run_server
from .napcat.handler import handle_raw_event
from .napcat.pipeline import persist_event
from .persistence.config import load_postgres_config
from .persistence.db import close_db, init_db


async def _on_event(raw: dict[str, object]) -> None:
    await handle_raw_event(raw, persist_callback=persist_event)


def _install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _request_shutdown(sig: signal.Signals) -> None:
        if stop_event.is_set():
            return
        logger.info("Received {}. Starting graceful shutdown...", sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown, sig)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(
                    sig,
                    lambda _signum, _frame, _sig=sig: _request_shutdown(_sig),
                )
            except ValueError:
                continue


async def main() -> None:
    telemetry.init_telemetry()
    telemetry.install_error_hooks()
    shutdown_event = asyncio.Event()
    _install_shutdown_handlers(shutdown_event)

    napcat_config = load_napcat_config()
    pg_config = load_postgres_config()
    chat_image_config = load_chat_image_config()

    logger.info("Initializing PostgreSQL...")
    await init_db(pg_config)

    relay_task = asyncio.create_task(
        run_outbox_relay(chat_image_config, stop_event=shutdown_event),
        name="outbox-relay",
    )

    logger.info(
        "Starting NapCat reverse WS server: host={} port={} path={}",
        napcat_config.ws_host,
        napcat_config.ws_port,
        napcat_config.ws_path,
    )
    try:
        await run_server(
            napcat_config,
            on_event=_on_event,
            stop_event=shutdown_event,
        )
    finally:
        relay_task.cancel()
        with suppress(asyncio.CancelledError):
            await relay_task
        await close_nats_publisher()
        await close_db()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
