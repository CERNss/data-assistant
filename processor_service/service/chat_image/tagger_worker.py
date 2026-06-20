from __future__ import annotations

import argparse
import asyncio
import hashlib
import time
from pathlib import Path
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from loguru import logger

try:
    from opentelemetry import metrics, trace
except ImportError:
    metrics = None
    trace = None

from contracts.chat_image_task import TaskV2, decode_task

from .config import ChatImageConfig, load_chat_image_config
from .tagger_pipeline import (
    enqueue_tagger_task_payload,
    ensure_tagger_auto_run,
    run_tagger_once,
    run_tagger_until_empty,
)


class _NoOpTracer:
    def start_as_current_span(
        self, _name: str, attributes: dict[str, Any] | None = None
    ):
        from contextlib import nullcontext

        return nullcontext()


TRACER = (
    trace.get_tracer("data_assistant.processor.chat_image.tagger_worker")
    if trace is not None
    else _NoOpTracer()
)
METER = (
    metrics.get_meter("data_assistant.processor.chat_image.tagger_worker")
    if metrics is not None
    else None
)
MESSAGE_COUNTER = (
    METER.create_counter(
        "processor_nats_messages_total",
        description="NATS messages handled by outcome",
    )
    if METER is not None
    else None
)
MESSAGE_LATENCY_MS = (
    METER.create_histogram(
        "processor_nats_message_handle_latency_ms",
        unit="ms",
        description="NATS message handling latency in milliseconds",
    )
    if METER is not None
    else None
)


async def handle_nats_message(
    *, config: ChatImageConfig, data: bytes, subject: str
) -> None:
    await _process_tagger_task_message(config=config, data=data, subject=subject)


async def _process_tagger_task_message(
    *, config: ChatImageConfig, data: bytes, subject: str
) -> bool:
    started_at = time.perf_counter()
    outcome = "failed"
    image_id_attr = ""

    with TRACER.start_as_current_span(
        "processor.handle_nats_message",
        attributes={
            "subject": subject,
            "payload_bytes": len(data),
        },
    ):
        try:
            task = decode_task(data)
        except Exception as exc:
            logger.warning("Ignore invalid NATS payload on {}: {}", subject, exc)
            outcome = "invalid_payload"
            _record_message_metrics(
                outcome=outcome,
                subject=subject,
                started_at=started_at,
                image_id=image_id_attr,
            )
            return True

        image_id_attr = str(task.image_id)
        image_path = _resolve_task_image_path(config, task)
        if image_path is None:
            logger.warning(
                "Ignore unresolved NATS payload on {}: image_id={} sha256={}",
                subject,
                task.image_id,
                task.sha256,
            )
            outcome = "unresolved_path"
            _record_message_metrics(
                outcome=outcome,
                subject=subject,
                started_at=started_at,
                image_id=image_id_attr,
            )
            return False

        payload = {
            "image_path": image_path,
            "context": task.context,
        }

        try:
            await enqueue_tagger_task_payload(config=config, payload=payload)
            if config.tagger.auto_run:
                await ensure_tagger_auto_run(config)
            outcome = "enqueued"
        except Exception as exc:
            logger.warning("Failed to process NATS payload on {}: {}", subject, exc)
            outcome = "failed"
            success = False
        else:
            success = True

    _record_message_metrics(
        outcome=outcome,
        subject=subject,
        started_at=started_at,
        image_id=image_id_attr,
    )
    return success


def _resolve_task_image_path(config: ChatImageConfig, task: TaskV2) -> str | None:
    if task.image_path:
        candidate = Path(task.image_path).expanduser()
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

    legacy_path = task.context.get("image_path")
    if isinstance(legacy_path, str) and legacy_path.strip():
        candidate = Path(legacy_path.strip()).expanduser()
        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

    chat_type = str(task.context.get("chat_type") or "").strip()
    chat_id = str(task.context.get("chat_id") or "").strip()
    message_id = str(task.context.get("message_id") or "").strip()
    seq_value = task.context.get("seq")

    if not message_id:
        return None

    if isinstance(seq_value, bool):
        seq = None
    elif isinstance(seq_value, int):
        seq = seq_value
    elif isinstance(seq_value, str):
        try:
            seq = int(seq_value)
        except ValueError:
            seq = None
    else:
        seq = None

    search_root = config.save_root
    if chat_type and chat_id:
        search_root = search_root / chat_type / chat_id

    if not search_root.exists() or not search_root.is_dir():
        return None

    if seq is None:
        pattern = f"*_{message_id}_*"
    else:
        pattern = f"*_{message_id}_{seq}_*"

    candidates = [path for path in search_root.glob(pattern) if path.is_file()]
    if not candidates:
        return None

    expected_sha = task.sha256.strip()
    if expected_sha:
        for candidate in candidates:
            if _file_sha256(candidate) == expected_sha:
                return str(candidate.resolve())

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(candidates[0].resolve())


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_message_metrics(
    *,
    outcome: str,
    subject: str,
    started_at: float,
    image_id: str,
) -> None:
    attributes = {
        "outcome": outcome,
        "subject": subject,
    }
    if image_id:
        attributes["has_image_id"] = "true"
    else:
        attributes["has_image_id"] = "false"
    if MESSAGE_COUNTER is not None:
        MESSAGE_COUNTER.add(1, attributes)
    if MESSAGE_LATENCY_MS is not None:
        latency_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
        MESSAGE_LATENCY_MS.record(latency_ms, attributes)


def _make_nats_lifecycle_callbacks(
    shutdown_event: asyncio.Event, nats_closed: asyncio.Event
) -> tuple[Any, Any, Any, Any]:
    """Build NATS connection lifecycle callbacks.

    The closed callback flips ``nats_closed`` and wakes ``shutdown_event`` so the
    worker exits and gets restarted, unless a graceful shutdown is already in
    progress (in which case the close is expected and ignored).
    """

    async def _on_error(exc: Exception) -> None:
        logger.warning("NATS worker connection error: {}", exc)

    async def _on_disconnected() -> None:
        logger.warning("NATS worker disconnected; reconnecting...")

    async def _on_reconnected() -> None:
        logger.info("NATS worker reconnected")

    async def _on_closed() -> None:
        if shutdown_event.is_set():
            return
        logger.error("NATS worker connection closed permanently; requesting restart")
        nats_closed.set()
        shutdown_event.set()

    return _on_error, _on_disconnected, _on_reconnected, _on_closed


async def _run(
    process_backlog: bool,
    stop_event: asyncio.Event | None = None,
) -> int:
    config = load_chat_image_config()
    if not config.tagger.enabled:
        print("CHAT_IMAGE_TAGGER_ENABLED is false, tagger worker will not start.")
        return 1
    if not config.tagger.base_url:
        print("CHAT_IMAGE_TAGGER_BASE_URL is empty, tagger worker will not start.")
        return 1
    if not config.nats.enabled:
        print("CHAT_IMAGE_NATS_ENABLED is false, tagger worker will not start.")
        return 1
    try:
        _validate_jetstream_queue_config(config)
    except ValueError as exc:
        print(str(exc))
        return 1

    try:
        import nats  # type: ignore
    except Exception as exc:
        print(f"nats-py is required for worker mode: {exc}")
        return 1

    shutdown_event = stop_event or asyncio.Event()
    nats_closed = asyncio.Event()
    (
        on_nats_error,
        on_nats_disconnected,
        on_nats_reconnected,
        on_nats_closed,
    ) = _make_nats_lifecycle_callbacks(shutdown_event, nats_closed)

    # Reconnect forever so a transient NATS outage self-heals instead of
    # crash-looping; closed_cb is the safety net for a terminal close so the
    # worker can never end up silently alive-but-disconnected.
    nc = await nats.connect(
        servers=list(config.nats.servers),
        name=f"{config.nats.client_name}-worker",
        connect_timeout=config.nats.connect_timeout_sec,
        max_reconnect_attempts=-1,
        error_cb=on_nats_error,
        disconnected_cb=on_nats_disconnected,
        reconnected_cb=on_nats_reconnected,
        closed_cb=on_nats_closed,
    )

    async def _on_message(msg: Any) -> None:
        success = await _process_tagger_task_message(
            config=config, data=msg.data, subject=msg.subject
        )
        await _ack_or_nak_message(msg, success=success)

    if config.nats.jetstream_enabled:
        js = nc.jetstream()
        await _ensure_jetstream_stream(config, js)
        await js.subscribe(
            config.nats.subject,
            queue=config.nats.queue_group,
            cb=_on_message,
            durable=config.nats.durable_name,
            stream=config.nats.stream_name,
            manual_ack=True,
            config=_build_consumer_config(config),
        )
        logger.info(
            "Tagger worker subscribed with JetStream: servers={} stream={} subject={} durable={} queue_group={}",
            ",".join(config.nats.servers),
            config.nats.stream_name,
            config.nats.subject,
            config.nats.durable_name,
            config.nats.queue_group,
        )
    else:
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

    if process_backlog and await _is_tagger_healthy(config):
        backlog_summary = await run_tagger_until_empty(config)
        if backlog_summary["picked"] > 0:
            logger.info(
                "Processed local backlog after subscribe: picked={} success={} failed={} requeued={}",
                backlog_summary["picked"],
                backlog_summary["success"],
                backlog_summary["failed"],
                backlog_summary["requeued"],
            )
    elif process_backlog:
        logger.warning(
            "Skip local backlog after subscribe because tagger is not healthy: base_url={}",
            config.tagger.base_url,
        )

    drain_task = asyncio.create_task(
        _periodic_queue_drain(config=config, stop_event=shutdown_event),
        name="tagger-queue-drain",
    )
    try:
        await shutdown_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass
        if not nc.is_closed:
            try:
                await nc.drain()
            except Exception as exc:
                logger.warning("Failed to drain NATS worker: {}", exc)
    # Non-zero exit when NATS closed under us, so the orchestrator restarts the
    # worker instead of leaving it parked without a live subscription.
    return 1 if nats_closed.is_set() else 0


def _validate_jetstream_queue_config(config: ChatImageConfig) -> None:
    if (
        config.nats.jetstream_enabled
        and config.nats.queue_group
        and config.nats.durable_name != config.nats.queue_group
    ):
        raise ValueError(
            "CHAT_IMAGE_NATS_DURABLE must equal CHAT_IMAGE_NATS_QUEUE_GROUP "
            "when JetStream queue subscriptions are enabled."
        )


def _build_consumer_config(config: ChatImageConfig) -> Any:
    try:
        from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
    except Exception as exc:
        raise RuntimeError("nats-py JetStream API is required") from exc

    return ConsumerConfig(
        durable_name=config.nats.durable_name,
        deliver_policy=DeliverPolicy.ALL,
        ack_policy=AckPolicy.EXPLICIT,
        ack_wait=config.nats.ack_wait_sec,
        max_deliver=config.nats.max_deliver,
        filter_subject=config.nats.subject,
        deliver_group=config.nats.queue_group,
    )


async def _ensure_jetstream_stream(config: ChatImageConfig, js: Any) -> None:
    try:
        from nats.js.api import RetentionPolicy, StorageType, StreamConfig
    except Exception as exc:
        raise RuntimeError("nats-py JetStream API is required") from exc

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
            )
        )
        logger.info(
            "Created JetStream stream: stream={} subjects={}",
            config.nats.stream_name,
            ",".join(config.nats.stream_subjects),
        )
    else:
        existing_subjects = list(getattr(stream_info.config, "subjects", []) or [])
        missing_subjects = [
            subject for subject in desired_subjects if subject not in existing_subjects
        ]
        if missing_subjects:
            stream_config = stream_info.config
            stream_config.subjects = [*existing_subjects, *missing_subjects]
            await js.update_stream(config=stream_config)
            logger.info(
                "Updated JetStream stream subjects: stream={} added_subjects={}",
                config.nats.stream_name,
                ",".join(missing_subjects),
            )


async def _periodic_queue_drain(
    *, config: ChatImageConfig, stop_event: asyncio.Event
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=config.tagger.drain_interval_sec
            )
            return
        except asyncio.TimeoutError:
            pass

        if not await _is_tagger_healthy(config):
            logger.warning(
                "Skip periodic tagger queue drain because tagger is not healthy: base_url={}",
                config.tagger.base_url,
            )
            continue

        try:
            summary = await run_tagger_once(config)
        except Exception as exc:
            logger.warning("Periodic tagger queue drain failed: {}", exc)
            continue

        if summary["picked"] > 0:
            logger.info(
                "Periodic tagger queue drain done: picked={} success={} failed={} requeued={}",
                summary["picked"],
                summary["success"],
                summary["failed"],
                summary["requeued"],
            )


async def _is_tagger_healthy(config: ChatImageConfig) -> bool:
    base_url = config.tagger.base_url
    if not config.tagger.enabled or not base_url:
        return False
    healthcheck_path = config.tagger.healthcheck_path
    if not healthcheck_path.startswith("/"):
        healthcheck_path = f"/{healthcheck_path}"
    timeout = ClientTimeout(total=min(5.0, config.tagger.drain_interval_sec))
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.get(f"{base_url}{healthcheck_path}") as response:
                return 200 <= response.status < 300
    except (asyncio.TimeoutError, ClientError):
        return False


async def _ack_or_nak_message(msg: Any, *, success: bool) -> None:
    try:
        metadata = getattr(msg, "metadata", None)
    except Exception:
        metadata = None
    if metadata is None:
        return
    try:
        if success:
            await msg.ack()
        else:
            await msg.nak()
    except Exception as exc:
        logger.warning("Failed to ack NATS message on {}: {}", msg.subject, exc)


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
