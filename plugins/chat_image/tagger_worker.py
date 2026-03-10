from __future__ import annotations

import argparse
import asyncio
from typing import Any

from loguru import logger

from .config import ChatImageConfig, load_chat_image_config
from .nats_task_bus import decode_tagger_task_payload
from .tagger_pipeline import (
    enqueue_tagger_task_payload,
    ensure_tagger_auto_run,
    run_tagger_once,
    run_tagger_until_empty,
)


async def handle_nats_message(
    *, config: ChatImageConfig, data: bytes, subject: str
) -> None:
    try:
        payload = decode_tagger_task_payload(data)
    except Exception as exc:
        logger.warning("Ignore invalid NATS payload on {}: {}", subject, exc)
        return

    try:
        await enqueue_tagger_task_payload(config=config, payload=payload)
        if config.tagger.auto_run:
            await ensure_tagger_auto_run(config)
        else:
            await run_tagger_once(config)
    except Exception as exc:
        logger.warning("Failed to process NATS payload on {}: {}", subject, exc)


async def _run(process_backlog: bool) -> int:
    config = load_chat_image_config()
    if not config.tagger.enabled:
        print("CHAT_IMAGE_TAGGER_ENABLED is false, tagger worker will not start.")
        return 1
    if config.tagger.tool_root is None:
        print("CHAT_IMAGE_TAGGER_TOOL_ROOT is empty, tagger worker will not start.")
        return 1
    if not config.nats.enabled:
        print("CHAT_IMAGE_NATS_ENABLED is false, tagger worker will not start.")
        return 1

    try:
        import nats  # type: ignore
    except Exception as exc:
        print(f"nats-py is required for worker mode: {exc}")
        return 1

    nc = await nats.connect(
        servers=list(config.nats.servers),
        name=f"{config.nats.client_name}-worker",
        connect_timeout=config.nats.connect_timeout_sec,
    )

    async def _on_message(msg: Any) -> None:
        await handle_nats_message(config=config, data=msg.data, subject=msg.subject)

    await nc.subscribe(
        config.nats.subject,
        queue=config.nats.queue_group,
        cb=_on_message,
    )
    logger.info(
        "Tagger worker subscribed: servers={} subject={} queue_group={}",
        ",".join(config.nats.servers),
        config.nats.subject,
        config.nats.queue_group,
    )

    if process_backlog:
        backlog_summary = await run_tagger_until_empty(config)
        if backlog_summary["picked"] > 0:
            logger.info(
                "Processed local backlog after subscribe: picked={} success={} failed={} requeued={}",
                backlog_summary["picked"],
                backlog_summary["success"],
                backlog_summary["failed"],
                backlog_summary["requeued"],
            )

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        await nc.drain()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run chat-image tagger worker with NATS."
    )
    parser.add_argument(
        "--skip-backlog",
        action="store_true",
        help="Skip local queue backlog processing before NATS subscribe.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(process_backlog=not args.skip_backlog)))


if __name__ == "__main__":
    main()
