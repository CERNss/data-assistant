from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from nonebot import logger

from .config import ChatImageConfig


NATS_CLIENT: Any | None = None
NATS_CONNECT_LOCK = asyncio.Lock()


def build_tagger_task_payload(*, image_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_path": str(image_path.resolve()),
        "context": context,
    }


def encode_tagger_task_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def decode_tagger_task_payload(data: bytes) -> dict[str, Any]:
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    image_path = payload.get("image_path")
    context = payload.get("context", {})
    if not isinstance(image_path, str) or not image_path.strip():
        raise ValueError("payload.image_path is empty")
    if not isinstance(context, dict):
        raise ValueError("payload.context is not an object")
    return {
        "image_path": image_path.strip(),
        "context": context,
    }


async def publish_tagger_task(config: ChatImageConfig, *, image_path: Path, context: dict[str, Any]) -> bool:
    if not config.nats.enabled:
        return False
    payload = build_tagger_task_payload(image_path=image_path, context=context)
    data = encode_tagger_task_payload(payload)
    try:
        client = await _get_or_connect_nats(config)
        await client.publish(config.nats.subject, data)
        await client.flush(timeout=config.nats.publish_timeout_sec)
        return True
    except Exception as exc:
        logger.warning(
            "Failed to publish tagger task to NATS: subject={} image_path={} error={}",
            config.nats.subject,
            payload["image_path"],
            exc,
        )
        return False


async def close_nats_publisher() -> None:
    global NATS_CLIENT
    async with NATS_CONNECT_LOCK:
        if NATS_CLIENT is None:
            return
        try:
            if getattr(NATS_CLIENT, "is_connected", False):
                await NATS_CLIENT.drain()
        except Exception as exc:  # pragma: no cover - defensive close path
            logger.warning("Failed to drain NATS publisher: {}", exc)
        finally:
            NATS_CLIENT = None


async def _get_or_connect_nats(config: ChatImageConfig) -> Any:
    global NATS_CLIENT
    if NATS_CLIENT is not None and getattr(NATS_CLIENT, "is_connected", False):
        return NATS_CLIENT

    async with NATS_CONNECT_LOCK:
        if NATS_CLIENT is not None and getattr(NATS_CLIENT, "is_connected", False):
            return NATS_CLIENT

        try:
            import nats  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("nats-py is required for NATS integration") from exc

        client = await nats.connect(
            servers=list(config.nats.servers),
            name=f"{config.nats.client_name}-publisher",
            connect_timeout=config.nats.connect_timeout_sec,
        )
        NATS_CLIENT = client
        logger.info(
            "Connected NATS publisher: servers={} subject={}",
            ",".join(config.nats.servers),
            config.nats.subject,
        )
        return NATS_CLIENT
