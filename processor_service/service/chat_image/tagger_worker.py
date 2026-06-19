from __future__ import annotations

import argparse
import asyncio
import hashlib
import time
from pathlib import Path
from typing import Any

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
            return

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
            return

        payload = {
            "image_path": image_path,
            "context": task.context,
        }

        try:
            await enqueue_tagger_task_payload(config=config, payload=payload)
            if config.tagger.auto_run:
                await ensure_tagger_auto_run(config)
            else:
                await run_tagger_once(config)
            outcome = "enqueued"
        except Exception as exc:
            logger.warning("Failed to process NATS payload on {}: {}", subject, exc)
            outcome = "failed"

    _record_message_metrics(
        outcome=outcome,
        subject=subject,
        started_at=started_at,
        image_id=image_id_attr,
    )


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

    shutdown_event = stop_event or asyncio.Event()
    try:
        await shutdown_event.wait()
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
