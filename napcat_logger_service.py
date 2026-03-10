from __future__ import annotations

import asyncio

from loguru import logger

import telemetry
from plugins.napcat.config import load_napcat_config
from plugins.napcat.connection import run_server
from plugins.napcat.handler import handle_raw_event
from plugins.napcat.pipeline import persist_event
from plugins.persistence.config import load_postgres_config
from plugins.persistence.db import close_db, init_db


async def _on_event(raw: dict) -> None:
    await handle_raw_event(raw, persist_callback=persist_event)


async def main() -> None:
    telemetry.init_telemetry()
    telemetry.install_error_hooks()

    napcat_config = load_napcat_config()
    pg_config = load_postgres_config()

    logger.info("Initializing PostgreSQL...")
    await init_db(pg_config)

    logger.info(
        "Starting NapCat reverse WS server: host={} port={} path={}",
        napcat_config.ws_host,
        napcat_config.ws_port,
        napcat_config.ws_path,
    )
    try:
        await run_server(napcat_config, on_event=_on_event)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
