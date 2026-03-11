from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from loguru import logger

try:
    from opentelemetry import metrics, trace
except ImportError:
    metrics = None
    trace = None

from contracts.chat_image_task import TASK_VERSION, TaskV2, encode_task

from .config import ChatImageConfig


class _NoOpTracer:
    def start_as_current_span(
        self, _name: str, attributes: dict[str, Any] | None = None
    ):
        from contextlib import nullcontext

        return nullcontext()


TRACER = (
    trace.get_tracer("data_assistant.logger.chat_image.nats_publisher")
    if trace is not None
    else _NoOpTracer()
)
METER = (
    metrics.get_meter("data_assistant.logger.chat_image.nats_publisher")
    if metrics is not None
    else None
)
NATS_PUBLISH_COUNTER = (
    METER.create_counter(
        "logger_nats_publish_total",
        description="Total NATS publish attempts by outcome",
    )
    if METER is not None
    else None
)
NATS_PUBLISH_LATENCY_MS = (
    METER.create_histogram(
        "logger_nats_publish_latency_ms",
        unit="ms",
        description="NATS publish latency in milliseconds",
    )
    if METER is not None
    else None
)


_nats_client: Any | None = None
_nats_connect_lock = asyncio.Lock()


def build_tagger_task_payload(
    *,
    image_id: int,
    sha256: str,
    source_url: str,
    original_url: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    task = TaskV2(
        version=TASK_VERSION,
        image_id=image_id,
        sha256=sha256,
        source_url=source_url,
        original_url=original_url or source_url,
        context=context,
    )
    return json.loads(encode_task(task).decode("utf-8"))


async def publish_tagger_task_with_result(
    config: ChatImageConfig,
    *,
    payload: dict[str, Any],
) -> tuple[bool, str | None]:
    image_id = str(payload.get("image_id") or "")
    start_time = time.perf_counter()

    with TRACER.start_as_current_span(
        "chat_image.nats_publish",
        attributes={
            "chat.image.nats.subject": config.nats.subject,
            "chat.image.id": image_id,
        },
    ):
        if not config.nats.enabled:
            _record_publish_metrics(
                outcome="disabled",
                subject=config.nats.subject,
                started_at=start_time,
            )
            return False, "nats_disabled"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            client = await _get_or_connect_nats(config)
            await client.publish(config.nats.subject, data)
            await client.flush(timeout=config.nats.publish_timeout_sec)
            _record_publish_metrics(
                outcome="published",
                subject=config.nats.subject,
                started_at=start_time,
            )
            return True, None
        except Exception as exc:
            logger.warning(
                "Failed to publish tagger task to NATS: subject={} image_id={} error={}",
                config.nats.subject,
                payload.get("image_id"),
                exc,
            )
            _record_publish_metrics(
                outcome="failed",
                subject=config.nats.subject,
                started_at=start_time,
            )
            return False, str(exc)


async def close_nats_publisher() -> None:
    global _nats_client
    async with _nats_connect_lock:
        if _nats_client is None:
            return
        try:
            if getattr(_nats_client, "is_connected", False):
                await _nats_client.drain()
        except Exception as exc:
            logger.warning("Failed to drain NATS publisher: {}", exc)
        finally:
            _nats_client = None


async def _get_or_connect_nats(config: ChatImageConfig) -> Any:
    global _nats_client
    if _nats_client is not None and getattr(_nats_client, "is_connected", False):
        return _nats_client

    async with _nats_connect_lock:
        if _nats_client is not None and getattr(_nats_client, "is_connected", False):
            return _nats_client

        try:
            import nats  # type: ignore
        except Exception as exc:
            raise RuntimeError("nats-py is required for NATS integration") from exc

        client = await nats.connect(
            servers=list(config.nats.servers),
            name=f"{config.nats.client_name}-publisher",
            connect_timeout=config.nats.connect_timeout_sec,
        )
        _nats_client = client
        logger.info(
            "Connected NATS publisher: servers={} subject={}",
            ",".join(config.nats.servers),
            config.nats.subject,
        )
        return _nats_client


def _record_publish_metrics(*, outcome: str, subject: str, started_at: float) -> None:
    attributes = {
        "outcome": outcome,
        "subject": subject,
    }
    if NATS_PUBLISH_COUNTER is not None:
        NATS_PUBLISH_COUNTER.add(1, attributes)
    if NATS_PUBLISH_LATENCY_MS is not None:
        latency_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
        NATS_PUBLISH_LATENCY_MS.record(latency_ms, attributes)
