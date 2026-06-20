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
_jetstream_context: Any | None = None
_ensured_streams: set[tuple[str, tuple[str, ...]]] = set()
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
    msg_id: str | None = None,
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
        # Stable dedup id (defaults to image_id) so an outbox replay of an
        # already-delivered message is de-duplicated by JetStream.
        dedup_id = msg_id or (image_id or None)
        headers = {"Nats-Msg-Id": dedup_id} if dedup_id else None
        try:
            client = await _get_or_connect_nats(config)
            if config.nats.jetstream_enabled:
                js = await _get_or_create_jetstream(config, client)
                await _ensure_stream(config, js)
                await js.publish(
                    config.nats.subject,
                    data,
                    timeout=config.nats.publish_timeout_sec,
                    stream=config.nats.stream_name,
                    headers=headers,
                )
            else:
                await client.publish(config.nats.subject, data, headers=headers)
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
    global _ensured_streams, _jetstream_context, _nats_client
    async with _nats_connect_lock:
        if _nats_client is None:
            return
        try:
            if getattr(_nats_client, "is_connected", False):
                await _nats_client.drain()
        except Exception as exc:
            logger.warning("Failed to drain NATS publisher: {}", exc)
        finally:
            _ensured_streams = set()
            _jetstream_context = None
            _nats_client = None


async def _get_or_connect_nats(config: ChatImageConfig) -> Any:
    global _ensured_streams, _jetstream_context, _nats_client
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
        _ensured_streams = set()
        _jetstream_context = None
        _nats_client = client
        logger.info(
            "Connected NATS publisher: servers={} subject={}",
            ",".join(config.nats.servers),
            config.nats.subject,
        )
        return _nats_client


async def _get_or_create_jetstream(config: ChatImageConfig, client: Any) -> Any:
    global _jetstream_context
    if _jetstream_context is not None:
        return _jetstream_context
    _jetstream_context = client.jetstream()
    logger.info(
        "Using JetStream publisher: stream={} subjects={}",
        config.nats.stream_name,
        ",".join(config.nats.stream_subjects),
    )
    return _jetstream_context


async def _ensure_stream(config: ChatImageConfig, js: Any) -> None:
    stream_key = (config.nats.stream_name, config.nats.stream_subjects)
    if stream_key in _ensured_streams:
        return

    try:
        from nats.js.api import RetentionPolicy, StorageType, StreamConfig
    except Exception as exc:
        raise RuntimeError("nats-py JetStream API is required") from exc

    max_age = (
        config.nats.stream_max_age_sec
        if config.nats.stream_max_age_sec > 0
        else None
    )
    max_bytes = config.nats.stream_max_bytes
    max_msgs = config.nats.stream_max_msgs

    desired_subjects = list(config.nats.stream_subjects)
    try:
        stream_info = await js.stream_info(config.nats.stream_name)
    except Exception:
        await js.add_stream(
            config=StreamConfig(
                name=config.nats.stream_name,
                subjects=desired_subjects,
                retention=RetentionPolicy.LIMITS,
                storage=StorageType.FILE,
                max_age=max_age,
                max_bytes=max_bytes,
                max_msgs=max_msgs,
            )
        )
        logger.info(
            "Created JetStream stream: stream={} subjects={} max_age_sec={} "
            "max_bytes={} max_msgs={}",
            config.nats.stream_name,
            ",".join(config.nats.stream_subjects),
            max_age,
            max_bytes,
            max_msgs,
        )
    else:
        stream_config = stream_info.config
        existing_subjects = list(getattr(stream_config, "subjects", []) or [])
        missing_subjects = [
            subject for subject in desired_subjects if subject not in existing_subjects
        ]
        needs_update = False
        if missing_subjects:
            stream_config.subjects = [*existing_subjects, *missing_subjects]
            needs_update = True
        if getattr(stream_config, "max_age", None) != max_age:
            stream_config.max_age = max_age
            needs_update = True
        if getattr(stream_config, "max_bytes", None) != max_bytes:
            stream_config.max_bytes = max_bytes
            needs_update = True
        if getattr(stream_config, "max_msgs", None) != max_msgs:
            stream_config.max_msgs = max_msgs
            needs_update = True
        if needs_update:
            await js.update_stream(config=stream_config)
            logger.info(
                "Reconciled JetStream stream: stream={} max_age_sec={} "
                "max_bytes={} max_msgs={}",
                config.nats.stream_name,
                max_age,
                max_bytes,
                max_msgs,
            )

    _ensured_streams.add(stream_key)


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
