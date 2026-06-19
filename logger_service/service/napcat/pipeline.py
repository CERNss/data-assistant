from __future__ import annotations

import hashlib
import importlib
import io
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from loguru import logger

try:
    from opentelemetry import metrics, trace
except ImportError:
    metrics = None
    trace = None

from .config import NapCatConfig, load_napcat_config
from .event import ImageSegment, OneBotEvent
from .handler import RefreshResult, is_probably_expired_url_error, refresh_image_url


class _NoOpTracer:
    def start_as_current_span(
        self, _name: str, attributes: dict[str, Any] | None = None
    ):
        from contextlib import nullcontext

        return nullcontext()


TRACER = (
    trace.get_tracer("data_assistant.logger.napcat.pipeline")
    if trace is not None
    else _NoOpTracer()
)
METER = (
    metrics.get_meter("data_assistant.logger.napcat.pipeline")
    if metrics is not None
    else None
)
EVENT_COUNTER = (
    METER.create_counter(
        "logger_events_total",
        description="Total logger events by persist outcome",
    )
    if METER is not None
    else None
)
IMAGE_COUNTER = (
    METER.create_counter(
        "logger_images_total",
        description="Total logger image processing outcomes",
    )
    if METER is not None
    else None
)
IMAGE_PROCESS_DURATION_MS = (
    METER.create_histogram(
        "logger_image_process_duration_ms",
        unit="ms",
        description="Image process duration in milliseconds",
    )
    if METER is not None
    else None
)


def _attempts_from_error(exc: Exception, default_attempts: int) -> int:
    attempts_raw = getattr(exc, "attempts", None)
    if isinstance(attempts_raw, int) and attempts_raw > 0:
        return attempts_raw
    return max(1, default_attempts)


def _refresh_trace_payload(result: RefreshResult) -> dict[str, Any]:
    return {
        "url": result.url,
        "final_phase": result.final_phase,
        "error": result.error,
        "attempts": [asdict(attempt) for attempt in result.attempts],
    }


def _build_failure_error(error: Exception, refresh_result: RefreshResult | None) -> str:
    if refresh_result is None:
        return str(error)
    payload = {
        "error": str(error),
        "refresh": _refresh_trace_payload(refresh_result),
    }
    return json.dumps(payload, ensure_ascii=False)


def _derive_stream_state(image: ImageSegment) -> tuple[str, str | None, str | None]:
    transfer_mode = "normal"
    stream_phase: str | None = None
    stream_data_type: str | None = None

    segment = image.raw_segment if isinstance(image.raw_segment, dict) else {}
    raw_data = segment.get("data")
    if isinstance(raw_data, dict):
        data: dict[str, Any] = raw_data
    else:
        data = {}

    phase_candidate = data.get("type")
    if isinstance(phase_candidate, str) and phase_candidate in {
        "stream",
        "response",
        "error",
    }:
        transfer_mode = "stream"
        stream_phase = phase_candidate

    data_type_candidate = data.get("data_type")
    if isinstance(data_type_candidate, str) and data_type_candidate.strip():
        stream_data_type = data_type_candidate.strip()

    return transfer_mode, stream_phase, stream_data_type


def _record_event_metric(*, outcome: str, post_type: str) -> None:
    if EVENT_COUNTER is None:
        return
    EVENT_COUNTER.add(
        1,
        {
            "outcome": outcome,
            "post_type": post_type,
        },
    )


def _record_image_metrics(
    *, outcome: str, transfer_mode: str, started_at: float
) -> None:
    attributes = {
        "outcome": outcome,
        "transfer_mode": transfer_mode,
    }
    if IMAGE_COUNTER is not None:
        IMAGE_COUNTER.add(1, attributes)
    if IMAGE_PROCESS_DURATION_MS is not None:
        latency_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
        IMAGE_PROCESS_DURATION_MS.record(latency_ms, attributes)


async def persist_event(event: OneBotEvent) -> None:
    from ..chat_image.config import load_chat_image_config
    from ..persistence.repository import (
        extract_plain_text,
        extract_sender_fields,
        insert_event,
        insert_message,
    )

    chat_config = load_chat_image_config()
    napcat_config = load_napcat_config()
    event_time = datetime.fromtimestamp(event.time, tz=UTC)

    with TRACER.start_as_current_span(
        "logger.persist_event",
        attributes={
            "post_type": event.post_type,
            "message_type": event.message_type or "",
        },
    ):
        try:
            event_id = await insert_event(
                post_type=event.post_type,
                message_type=event.message_type,
                user_id=event.user_id,
                group_id=event.group_id,
                group_name=event.group_name,
                self_id=event.self_id,
                message_id=event.message_id,
                event_time=event_time,
                raw_message=event.raw_message,
                raw=event.raw,
            )
        except Exception as exc:
            logger.error(
                "Failed to insert event to DB: post_type={} message_id={} error={}",
                event.post_type,
                event.message_id,
                exc,
            )
            _record_event_metric(outcome="db_failed", post_type=event.post_type)
            return

        _record_event_metric(outcome="persisted", post_type=event.post_type)

        if event.post_type not in {"message", "message_sent"}:
            return

        message_type = event.message_type or (
            "group" if event.group_id is not None else "private"
        )
        user_id = event.self_id if event.post_type == "message_sent" else event.user_id
        sender_nickname, sender_card, sender_role = extract_sender_fields(event.sender)
        if message_type == "private":
            sender_card = None
            sender_role = None

        try:
            await insert_message(
                event_id=event_id,
                message_type=message_type,
                user_id=user_id if user_id is not None else event.self_id,
                group_id=event.group_id,
                group_name=event.group_name,
                sender_nickname=sender_nickname,
                sender_card=sender_card,
                sender_role=sender_role,
                message_id=event.message_id,
                plain_text=extract_plain_text(
                    event.message_segments, event.raw_message
                ),
                message_segments=event.message_segments,
                event_time=event_time,
            )
        except Exception as exc:
            logger.error(
                "Failed to insert structured message: post_type={} message_id={} error={}",
                event.post_type,
                event.message_id,
                exc,
            )

        if not event.images:
            return

        for image in event.images:
            with TRACER.start_as_current_span(
                "logger.process_image",
                attributes={
                    "event_id": event_id,
                    "seq": image.seq,
                },
            ):
                await _process_image(
                    event_id=event_id,
                    event=event,
                    image=image,
                    chat_config=chat_config,
                    napcat_config=napcat_config,
                )


async def _process_image(
    *,
    event_id: int,
    event: OneBotEvent,
    image: ImageSegment,
    chat_config: Any,
    napcat_config: NapCatConfig,
) -> None:
    from ..chat_image.audit import append_json_line
    from ..chat_image.downloader import download_image_with_retry
    from ..chat_image.nats_publisher import (
        build_tagger_task_payload,
        publish_tagger_task_with_result,
    )
    from ..chat_image.storage import build_image_save_path
    from ..persistence.db import get_pool
    from ..persistence.repository import (
        insert_image,
        insert_nats_dispatch,
        update_image_download_duplicate,
        update_image_download_failure,
        update_image_download_success,
        update_image_refresh_trace,
    )

    chat_type = event.message_type or "unknown"
    chat_id = str(event.group_id or event.user_id or "unknown")
    message_id = event.message_id or "unknown"
    original_url = image.url_decoded or image.url_raw
    transfer_mode, stream_phase, stream_data_type = _derive_stream_state(image)
    process_started_at = time.perf_counter()

    try:
        image_id = await insert_image(
            event_id=event_id,
            seq=image.seq,
            url_raw=image.url_raw,
            url_decoded=image.url_decoded,
            file_name=image.file_name,
            sub_type=image.sub_type,
            file_size=image.file_size,
            summary=image.summary,
        )
    except Exception as exc:
        logger.error(
            "Failed to insert image row: event_id={} seq={} error={}",
            event_id,
            image.seq,
            exc,
        )
        _record_image_metrics(
            outcome="insert_failed",
            transfer_mode=transfer_mode,
            started_at=process_started_at,
        )
        return

    async def _mark_failed(
        *,
        error_text: str,
        attempt_count: int,
        current_url: str | None,
        refresh_result: RefreshResult | None,
        failure_phase: str | None,
    ) -> None:
        try:
            await update_image_download_failure(
                image_id,
                error=error_text,
                download_attempt=attempt_count,
                stream_phase=failure_phase,
                transfer_mode=transfer_mode,
                stream_data_type=stream_data_type,
            )
        except Exception as db_exc:
            logger.error(
                "Failed to update image failure status: event_id={} image_id={} error={}",
                event_id,
                image_id,
                db_exc,
            )

        append_json_line(
            chat_config.audit_log_file,
            {
                "logged_at": datetime.now(UTC).isoformat(),
                "event_id": event_id,
                "image_id": image_id,
                "seq": image.seq,
                "url": current_url,
                "status": "failed",
                "error": error_text,
                "download_attempt": attempt_count,
                "refresh": _refresh_trace_payload(refresh_result)
                if refresh_result is not None
                else None,
            },
        )
        _record_image_metrics(
            outcome="failed",
            transfer_mode=transfer_mode,
            started_at=process_started_at,
        )

    if not original_url:
        await _mark_failed(
            error_text="missing_image_url",
            attempt_count=0,
            current_url=None,
            refresh_result=None,
            failure_phase=stream_phase or "error",
        )
        return

    active_url = original_url
    refresh_result: RefreshResult | None = None
    downloaded_image = None
    total_attempt_count = 0

    try:
        downloaded_image, first_attempt_count = await download_image_with_retry(
            active_url,
            chat_config,
        )
        total_attempt_count += first_attempt_count
    except Exception as first_error:
        total_attempt_count += _attempts_from_error(
            first_error, chat_config.retry_count
        )
        if not is_probably_expired_url_error(first_error):
            await _mark_failed(
                error_text=str(first_error),
                attempt_count=total_attempt_count,
                current_url=active_url,
                refresh_result=None,
                failure_phase=stream_phase,
            )
            return

        refresh_result = await refresh_image_url(
            image.file_name,
            napcat_config,
            message_id=event.message_id,
        )

        if refresh_result.attempts:
            try:
                await update_image_refresh_trace(
                    image_id,
                    refresh_attempt_count=len(refresh_result.attempts),
                    refresh_trace=_refresh_trace_payload(refresh_result),
                )
            except Exception as db_exc:
                logger.error(
                    "Failed to update refresh trace: event_id={} image_id={} error={}",
                    event_id,
                    image_id,
                    db_exc,
                )

        if refresh_result.url is None:
            await _mark_failed(
                error_text=_build_failure_error(first_error, refresh_result),
                attempt_count=total_attempt_count,
                current_url=active_url,
                refresh_result=refresh_result,
                failure_phase=refresh_result.final_phase,
            )
            return

        active_url = refresh_result.url
        try:
            downloaded_image, refresh_attempt_count = await download_image_with_retry(
                active_url,
                chat_config,
            )
            total_attempt_count += refresh_attempt_count
        except Exception as second_error:
            total_attempt_count += _attempts_from_error(
                second_error, chat_config.retry_count
            )
            await _mark_failed(
                error_text=_build_failure_error(second_error, refresh_result),
                attempt_count=total_attempt_count,
                current_url=active_url,
                refresh_result=refresh_result,
                failure_phase=refresh_result.final_phase,
            )
            return

    if downloaded_image is None:
        await _mark_failed(
            error_text="download_result_missing",
            attempt_count=max(1, total_attempt_count),
            current_url=active_url,
            refresh_result=refresh_result,
            failure_phase=stream_phase,
        )
        return

    raw_bytes = downloaded_image.body
    hash_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    save_path = build_image_save_path(
        save_root=chat_config.save_root,
        chat_type=chat_type,
        chat_id=chat_id,
        message_id=message_id,
        attachment_index=image.seq,
        filename=image.file_name,
        source_url=active_url,
    )

    fmt: str | None = None
    width: int | None = None
    height: int | None = None
    is_animated: bool | None = None
    frame_count: int | None = None
    try:
        pil_image_module = importlib.import_module("PIL.Image")

        with pil_image_module.open(io.BytesIO(raw_bytes)) as pil_image:
            fmt = pil_image.format
            width, height = pil_image.size
            n_frames = int(getattr(pil_image, "n_frames", 1))
            frame_count = n_frames
            is_animated = n_frames > 1
    except Exception as exc:
        logger.debug(
            "Pillow metadata extraction failed: event_id={} seq={} error={}",
            event_id,
            image.seq,
            exc,
        )

    pool = get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM onebot_message_images"
        " WHERE hash_sha256=$1 AND download_status='saved' LIMIT 1",
        hash_sha256,
    )
    if existing:
        try:
            await update_image_download_duplicate(
                image_id,
                hash_sha256=hash_sha256,
                download_attempt=max(1, total_attempt_count),
                transfer_mode=transfer_mode,
                stream_phase=stream_phase,
                stream_data_type=stream_data_type,
            )
        except Exception as db_exc:
            logger.error(
                "Failed to update duplicate status: event_id={} image_id={} error={}",
                event_id,
                image_id,
                db_exc,
            )
        append_json_line(
            chat_config.audit_log_file,
            {
                "logged_at": datetime.now(UTC).isoformat(),
                "event_id": event_id,
                "image_id": image_id,
                "seq": image.seq,
                "url": active_url,
                "status": "duplicate",
                "hash_sha256": hash_sha256,
                "download_attempt": max(1, total_attempt_count),
                "refresh": _refresh_trace_payload(refresh_result)
                if refresh_result is not None
                else None,
            },
        )
        _record_image_metrics(
            outcome="duplicate",
            transfer_mode=transfer_mode,
            started_at=process_started_at,
        )
        return

    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(raw_bytes)
    except Exception as exc:
        await _mark_failed(
            error_text=f"file_write_error: {exc}",
            attempt_count=max(1, total_attempt_count),
            current_url=active_url,
            refresh_result=refresh_result,
            failure_phase=stream_phase,
        )
        return

    success_phase = stream_phase
    success_stream_data_type = stream_data_type
    if refresh_result is not None:
        success_phase = refresh_result.final_phase
        if success_stream_data_type is None:
            success_stream_data_type = "url_refresh"

    try:
        await update_image_download_success(
            image_id,
            local_path=str(save_path),
            hash_sha256=hash_sha256,
            format=fmt,
            width=width,
            height=height,
            is_animated=is_animated,
            frame_count=frame_count,
            http_content_type=downloaded_image.content_type,
            http_content_length=downloaded_image.content_length,
            download_attempt=max(1, total_attempt_count),
            transfer_mode=transfer_mode,
            stream_phase=success_phase,
            stream_data_type=success_stream_data_type,
        )
    except Exception as db_exc:
        logger.error(
            "Failed to update image success status: event_id={} image_id={} error={}",
            event_id,
            image_id,
            db_exc,
        )
        append_json_line(
            chat_config.audit_log_file,
            {
                "logged_at": datetime.now(UTC).isoformat(),
                "event_id": event_id,
                "image_id": image_id,
                "seq": image.seq,
                "url": active_url,
                "status": "db_update_failed",
                "local_path": str(save_path),
                "size": len(raw_bytes),
                "hash_sha256": hash_sha256,
                "format": fmt,
                "download_attempt": max(1, total_attempt_count),
                "error": str(db_exc),
                "refresh": _refresh_trace_payload(refresh_result)
                if refresh_result is not None
                else None,
            },
        )
        _record_image_metrics(
            outcome="db_update_failed",
            transfer_mode=transfer_mode,
            started_at=process_started_at,
        )
        return

    append_json_line(
        chat_config.audit_log_file,
        {
            "logged_at": datetime.now(UTC).isoformat(),
            "event_id": event_id,
            "image_id": image_id,
            "seq": image.seq,
            "url": active_url,
            "status": "saved",
            "local_path": str(save_path),
            "size": len(raw_bytes),
            "hash_sha256": hash_sha256,
            "format": fmt,
            "download_attempt": max(1, total_attempt_count),
            "refresh": _refresh_trace_payload(refresh_result)
            if refresh_result is not None
            else None,
        },
    )

    tag_context: dict[str, Any] = {
        "event_id": event_id,
        "image_id": image_id,
        "post_type": event.post_type,
        "message_type": event.message_type,
        "chat_type": chat_type,
        "chat_id": chat_id,
        "user_id": event.user_id,
        "group_id": event.group_id,
        "message_id": message_id,
        "seq": image.seq,
        "source_url": active_url,
        "original_url": original_url,
    }

    nats_payload = build_tagger_task_payload(
        image_id=image_id,
        sha256=hash_sha256,
        source_url=active_url,
        original_url=original_url,
        context=tag_context,
    )
    published, publish_error = await publish_tagger_task_with_result(
        chat_config,
        payload=nats_payload,
    )

    nats_status: str
    nats_error: str | None = None
    if published:
        nats_status = "published"
    else:
        nats_status = "failed"
        nats_error = publish_error or "nats_publish_failed"

    try:
        await insert_nats_dispatch(
            image_id=image_id,
            subject=chat_config.nats.subject,
            payload=nats_payload,
            status=nats_status,
            error=nats_error,
        )
    except Exception as db_exc:
        logger.error(
            "Failed to insert NATS dispatch record: event_id={} image_id={} error={}",
            event_id,
            image_id,
            db_exc,
        )

    _record_image_metrics(
        outcome="saved",
        transfer_mode=transfer_mode,
        started_at=process_started_at,
    )
