from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from .config import ChatImageConfig
from .nats_publisher import publish_tagger_task_with_result


async def run_outbox_relay(
    config: ChatImageConfig, *, stop_event: asyncio.Event
) -> None:
    """Periodically re-publish saved-but-unhanded-off tagger tasks.

    The logger persists the NATS intent to ``onebot_nats_dispatches`` before it
    publishes (transactional outbox). If the publish failed or the process
    crashed before recording success, this relay drives those rows to NATS,
    guaranteeing that a saved image always reaches the bus even across a NATS
    outage — without depending on a live NATS at the moment of saving.
    """
    relay = config.outbox
    if not config.nats.enabled or not relay.enabled:
        return

    logger.info(
        "Outbox relay started: interval_sec={} batch_size={} max_attempts={}",
        relay.interval_sec,
        relay.batch_size,
        relay.max_attempts,
    )
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=relay.interval_sec)
            return
        except asyncio.TimeoutError:
            pass

        try:
            await relay_once(config)
        except Exception as exc:
            logger.warning("Outbox relay pass failed: {}", exc)


async def relay_once(config: ChatImageConfig) -> dict[str, int]:
    from ..persistence.repository import (
        fetch_unpublished_nats_dispatches,
        mark_nats_dispatch_failed,
        mark_nats_dispatch_published,
    )

    relay = config.outbox
    summary = {"picked": 0, "published": 0, "failed": 0}

    rows = await fetch_unpublished_nats_dispatches(
        limit=relay.batch_size,
        max_attempts=relay.max_attempts,
        min_age_sec=relay.min_age_sec,
    )
    summary["picked"] = len(rows)
    if not rows:
        return summary

    for row in rows:
        dispatch_id = int(row["id"])
        image_id = row.get("image_id")
        payload = _decode_payload(row.get("payload"))
        if payload is None:
            await mark_nats_dispatch_failed(
                dispatch_id, error="invalid outbox payload"
            )
            summary["failed"] += 1
            continue

        published, error = await publish_tagger_task_with_result(
            config,
            payload=payload,
            msg_id=str(image_id) if image_id is not None else None,
        )
        if published:
            await mark_nats_dispatch_published(dispatch_id)
            summary["published"] += 1
        else:
            await mark_nats_dispatch_failed(
                dispatch_id, error=error or "nats_publish_failed"
            )
            summary["failed"] += 1

    if summary["published"] or summary["failed"]:
        logger.info(
            "Outbox relay pass: picked={} published={} failed={}",
            summary["picked"],
            summary["published"],
            summary["failed"],
        )
    return summary


def _decode_payload(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None
