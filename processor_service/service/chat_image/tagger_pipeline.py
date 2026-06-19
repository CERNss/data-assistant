from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout
from loguru import logger

from .audit import append_json_line
from .config import ChatImageConfig

try:
    from opentelemetry import metrics, trace

    tracer = trace.get_tracer("data_assistant.processor.chat_image.tagger_pipeline")
    meter = metrics.get_meter("data_assistant.processor.chat_image.tagger_pipeline")
except ImportError:
    meter = None

    class _NoOpTracer:
        def start_as_current_span(
            self, name: str, attributes: dict[str, Any] | None = None
        ):
            from contextlib import nullcontext

            return nullcontext()

    tracer = _NoOpTracer()

QUEUE_ENQUEUE_COUNTER = (
    meter.create_counter(
        "processor_queue_enqueued_total",
        description="Queue enqueue attempts by outcome",
    )
    if meter is not None
    else None
)
QUEUE_DEPTH_HIST = (
    meter.create_histogram(
        "processor_queue_depth",
        description="Queue depth samples",
    )
    if meter is not None
    else None
)
TAGGER_BATCH_COUNTER = (
    meter.create_counter(
        "processor_tagger_batches_total",
        description="Tagger batch outcomes",
    )
    if meter is not None
    else None
)
TAGGER_ITEM_COUNTER = (
    meter.create_counter(
        "processor_tagger_items_total",
        description="Tagger item outcomes",
    )
    if meter is not None
    else None
)
TAGGER_BATCH_LATENCY_MS = (
    meter.create_histogram(
        "processor_tagger_batch_latency_ms",
        unit="ms",
        description="Tagger batch latency in milliseconds",
    )
    if meter is not None
    else None
)

QUEUE_LOCK = asyncio.Lock()
AUTO_RUN_LOCK = asyncio.Lock()
auto_run_task: asyncio.Task[None] | None = None

BatchItem = dict[str, Any]
BatchResult = dict[str, Any]
TaggerRunner = Callable[
    [ChatImageConfig, list[BatchItem]], Awaitable[list[BatchResult]]
]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _archive_corrupt_queue(queue_file: Path) -> Path | None:
    if not queue_file.exists():
        return None
    archive_path = queue_file.with_name(
        f"{queue_file.name}.corrupt.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    )
    counter = 1
    while archive_path.exists():
        archive_path = queue_file.with_name(
            f"{queue_file.name}.corrupt.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.{counter}"
        )
        counter += 1
    queue_file.replace(archive_path)
    return archive_path


def _load_queue(queue_file: Path) -> list[BatchItem]:
    if not queue_file.exists():
        return []
    try:
        payload = json.loads(queue_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        archive_path = _archive_corrupt_queue(queue_file)
        logger.warning(
            "Invalid tagger queue file archived: path={} archive_path={}",
            queue_file,
            archive_path,
        )
        return []
    if not isinstance(payload, list):
        archive_path = _archive_corrupt_queue(queue_file)
        logger.warning(
            "Unexpected tagger queue payload archived: path={} archive_path={}",
            queue_file,
            archive_path,
        )
        return []
    return [item for item in payload if isinstance(item, dict)]


def _save_queue(queue_file: Path, items: list[BatchItem]) -> None:
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = queue_file.with_suffix(queue_file.suffix + ".tmp")
    tmp_file.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_file.replace(queue_file)


def _inflight_file_for(queue_file: Path) -> Path:
    return queue_file.with_suffix(queue_file.suffix + ".inflight")


def _save_inflight(queue_file: Path, items: list[BatchItem]) -> None:
    _save_queue(_inflight_file_for(queue_file), items)


def _clear_inflight(queue_file: Path) -> None:
    inflight_file = _inflight_file_for(queue_file)
    if inflight_file.exists():
        inflight_file.unlink()


def _restore_inflight(queue_file: Path) -> None:
    inflight_file = _inflight_file_for(queue_file)
    inflight_items = _load_queue(inflight_file)
    if not inflight_items:
        _clear_inflight(queue_file)
        return

    queue_items = _load_queue(queue_file)
    queued_paths = {
        item.get("image_path")
        for item in queue_items
        if isinstance(item.get("image_path"), str)
    }
    restored_items = [
        item
        for item in inflight_items
        if not isinstance(item.get("image_path"), str)
        or item.get("image_path") not in queued_paths
    ]
    if restored_items:
        _save_queue(queue_file, restored_items + queue_items)
        logger.warning(
            "Restored inflight tagger queue items: path={} count={}",
            queue_file,
            len(restored_items),
        )
    _clear_inflight(queue_file)


def _append_tagger_audit(config: ChatImageConfig, payload: dict[str, Any]) -> None:
    append_json_line(
        config.tagger.audit_log_file,
        {
            "logged_at": _utc_now_iso(),
            **payload,
        },
    )


def _tail_text(text: str, limit: int = 800) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _build_tagger_request_payload(
    config: ChatImageConfig,
    image_paths: list[str],
) -> dict[str, Any]:
    tagger = config.tagger
    payload: dict[str, Any] = {"image_paths": image_paths}
    if tagger.threshold is not None:
        payload["threshold"] = tagger.threshold
    if tagger.use_chinese_name is not None:
        payload["use_chinese_name"] = tagger.use_chinese_name
    if tagger.top_k is not None:
        payload["top_k"] = tagger.top_k
    return payload


async def _post_tagger_batch(
    *,
    base_url: str,
    payload: dict[str, Any],
    timeout_sec: float,
) -> dict[str, Any]:
    timeout = ClientTimeout(total=timeout_sec)
    response_text = ""

    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{base_url}/tag/batch",
                json=payload,
            ) as response:
                response_text = await response.text()
                if response.status >= 400:
                    raise RuntimeError(
                        f"tagger http {response.status}: {_tail_text(response_text)}"
                    )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(f"tagger request timed out after {timeout_sec}s") from exc
    except ClientResponseError as exc:
        raise RuntimeError(f"tagger http {exc.status}: {exc.message}") from exc
    except ClientError as exc:
        raise RuntimeError(f"tagger request failed: {exc}") from exc

    try:
        payload_raw = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid tagger response JSON: {exc}") from exc
    if not isinstance(payload_raw, dict):
        raise RuntimeError("invalid tagger response payload")
    return payload_raw


def _normalize_batch_result(
    *,
    item: BatchItem,
    result_raw: Any,
) -> BatchResult:
    if not isinstance(result_raw, dict):
        return {
            "item": item,
            "status": "failed",
            "error": "invalid tagger response item",
        }

    if result_raw.get("success") is True:
        raw_tags = result_raw.get("tags", [])
        if not isinstance(raw_tags, list):
            return {
                "item": item,
                "status": "failed",
                "error": "tagger response tags is not a list",
            }
        tags: list[str] = []
        for raw_tag in raw_tags:
            if isinstance(raw_tag, dict):
                name = str(raw_tag.get("name", "")).strip()
            else:
                name = str(raw_tag).strip()
            if name:
                tags.append(name)
        return {
            "item": item,
            "status": "success",
            "tags": tags,
        }

    error_type = str(result_raw.get("error_type") or "").strip()
    error_message = str(result_raw.get("error") or "unknown tagger error")
    if error_type:
        error_message = f"{error_type}: {error_message}"
    return {
        "item": item,
        "status": "failed",
        "error": error_message,
    }


def _extract_result_image_path(result_raw: Any) -> str | None:
    if not isinstance(result_raw, dict):
        return None
    image_path_raw = result_raw.get("image_path")
    if not isinstance(image_path_raw, str) or not image_path_raw.strip():
        return None
    try:
        return str(Path(image_path_raw.strip()).expanduser().resolve())
    except OSError:
        return image_path_raw.strip()


async def _run_http_tagger_batch(
    config: ChatImageConfig, batch_items: list[BatchItem]
) -> list[BatchResult]:
    tagger = config.tagger
    if not tagger.base_url:
        raise RuntimeError("CHAT_IMAGE_TAGGER_BASE_URL is empty")

    pre_failures: list[BatchResult] = []
    ready_items: list[BatchItem] = []
    request_image_paths: list[str] = []

    for item in batch_items:
        source_path = Path(str(item.get("image_path", ""))).expanduser()
        if not source_path.exists():
            pre_failures.append(
                {
                    "item": item,
                    "status": "failed",
                    "error": f"image not found: {source_path}",
                }
            )
            continue
        if not source_path.is_file():
            pre_failures.append(
                {
                    "item": item,
                    "status": "failed",
                    "error": f"path is not a file: {source_path}",
                }
            )
            continue
        ready_items.append(item)
        request_image_paths.append(str(source_path.resolve()))

    if not ready_items:
        return pre_failures

    response_payload = await _post_tagger_batch(
        base_url=tagger.base_url,
        payload=_build_tagger_request_payload(config, request_image_paths),
        timeout_sec=tagger.timeout_sec,
    )
    raw_results = response_payload.get("results")
    if not isinstance(raw_results, list):
        raise RuntimeError("tagger response missing results list")

    if len(raw_results) != len(ready_items):
        logger.warning(
            "Tagger returned mismatched batch size: requested={} returned={}",
            len(ready_items),
            len(raw_results),
        )

    raw_results_by_path: dict[str, Any] = {}
    unmatched_results: list[Any] = []
    for result_raw in raw_results:
        result_path = _extract_result_image_path(result_raw)
        if result_path:
            raw_results_by_path[result_path] = result_raw
        else:
            unmatched_results.append(result_raw)

    result_list: list[BatchResult] = []
    fallback_index = 0
    for item, request_path in zip(ready_items, request_image_paths, strict=True):
        result_raw = raw_results_by_path.get(request_path)
        if result_raw is None and fallback_index < len(unmatched_results):
            result_raw = unmatched_results[fallback_index]
            fallback_index += 1
        if result_raw is None:
            result_list.append(
                {
                    "item": item,
                    "status": "failed",
                    "error": "missing result from tagger service",
                }
            )
            continue
        result_list.append(_normalize_batch_result(item=item, result_raw=result_raw))
    return pre_failures + result_list


async def enqueue_image_for_tagging(
    *,
    config: ChatImageConfig,
    image_path: Path,
    context: dict[str, Any],
) -> None:
    tagger = config.tagger
    if not tagger.enabled:
        return
    if not tagger.base_url:
        logger.warning(
            "Tagger is enabled but CHAT_IMAGE_TAGGER_BASE_URL is not configured"
        )
        return

    await enqueue_tagger_task_payload(
        config=config,
        payload={
            "image_path": str(image_path.resolve()),
            "context": context,
        },
    )


async def enqueue_tagger_task_payload(
    *,
    config: ChatImageConfig,
    payload: dict[str, Any],
) -> None:
    tagger = config.tagger

    queued_image_path_raw = payload.get("image_path")
    if not isinstance(queued_image_path_raw, str) or not queued_image_path_raw.strip():
        return
    queued_image_path = str(Path(queued_image_path_raw.strip()).resolve())
    context_raw = payload.get("context", {})
    context = context_raw if isinstance(context_raw, dict) else {}
    queue_item = {
        "image_path": queued_image_path,
        "context": context,
        "enqueued_at": _utc_now_iso(),
        "attempt_count": 0,
    }

    async with QUEUE_LOCK:
        queue_items = _load_queue(tagger.queue_file)
        if any(item.get("image_path") == queued_image_path for item in queue_items):
            _record_queue_metrics(outcome="duplicate", depth=len(queue_items))
            return
        queue_items.append(queue_item)
        _save_queue(tagger.queue_file, queue_items)
        _record_queue_metrics(outcome="enqueued", depth=len(queue_items))

    logger.info("Queued image for tagging: path={}", queued_image_path)
    if tagger.auto_run:
        await ensure_tagger_auto_run(config)


def get_pending_tagger_count(config: ChatImageConfig) -> int:
    if not config.tagger.enabled:
        return 0
    _restore_inflight(config.tagger.queue_file)
    return len(_load_queue(config.tagger.queue_file))


async def run_tagger_once(
    config: ChatImageConfig, *, runner: TaggerRunner | None = None
) -> dict[str, int]:
    tagger = config.tagger
    summary = {"picked": 0, "success": 0, "failed": 0, "requeued": 0}
    if not tagger.enabled or not tagger.base_url:
        return summary

    async with QUEUE_LOCK:
        _restore_inflight(tagger.queue_file)
        queue_items = _load_queue(tagger.queue_file)
        if not queue_items:
            return summary
        batch_items = queue_items[: tagger.batch_size]
        queue_items = queue_items[tagger.batch_size :]
        _save_inflight(tagger.queue_file, batch_items)
        _save_queue(tagger.queue_file, queue_items)
    summary["picked"] = len(batch_items)

    runner_impl = runner or _run_http_tagger_batch
    batch_started = time.perf_counter()

    with tracer.start_as_current_span(
        "chat_image.tagger.run_batch",
        attributes={
            "chat.image.tagger.batch_size": len(batch_items),
        },
    ):
        try:
            batch_results = await runner_impl(config, batch_items)
        except Exception as exc:  # pragma: no cover - protective fallback
            logger.warning("Tagger batch execution failed: {}", exc)
            batch_results = [
                {
                    "item": item,
                    "status": "failed",
                    "error": str(exc),
                }
                for item in batch_items
            ]

    result_by_path: dict[str, BatchResult] = {}
    for result in batch_results:
        item = result.get("item")
        if not isinstance(item, dict):
            continue
        image_path = str(item.get("image_path", ""))
        if not image_path:
            continue
        result_by_path[image_path] = result

    requeue_items: list[BatchItem] = []
    for item in batch_items:
        image_path = str(item.get("image_path", ""))
        result = result_by_path.get(image_path)
        if result is None:
            result = {
                "item": item,
                "status": "failed",
                "error": "missing result from tagger runner",
            }

        if result.get("status") == "success":
            tags = result.get("tags", [])
            tags = tags if isinstance(tags, list) else []
            summary["success"] += 1
            _append_tagger_audit(
                config,
                {
                    "status": "success",
                    "image_path": image_path,
                    "tag_count": len(tags),
                    "tags": tags,
                    "attempt_count": item.get("attempt_count", 0) + 1,
                    "context": item.get("context", {}),
                },
            )
            continue

        summary["failed"] += 1
        attempts = int(item.get("attempt_count", 0)) + 1
        error_message = str(result.get("error", "unknown tagger error"))
        if attempts < tagger.max_attempts:
            item["attempt_count"] = attempts
            requeue_items.append(item)
            summary["requeued"] += 1
            _append_tagger_audit(
                config,
                {
                    "status": "retrying",
                    "image_path": image_path,
                    "error": error_message,
                    "attempt_count": attempts,
                    "context": item.get("context", {}),
                },
            )
        else:
            _append_tagger_audit(
                config,
                {
                    "status": "failed",
                    "image_path": image_path,
                    "error": error_message,
                    "attempt_count": attempts,
                    "context": item.get("context", {}),
                },
            )

    if requeue_items:
        async with QUEUE_LOCK:
            queue_items = _load_queue(tagger.queue_file)
            _save_queue(tagger.queue_file, requeue_items + queue_items)
            _record_queue_metrics(
                outcome="requeued", depth=len(requeue_items + queue_items)
            )

    _clear_inflight(tagger.queue_file)
    _record_batch_metrics(summary=summary, started_at=batch_started)

    return summary


async def run_tagger_until_empty(
    config: ChatImageConfig, *, runner: TaggerRunner | None = None
) -> dict[str, int]:
    total = {"picked": 0, "success": 0, "failed": 0, "requeued": 0}
    while True:
        summary = await run_tagger_once(config, runner=runner)
        if summary["picked"] == 0:
            break
        for key in total:
            total[key] += summary[key]
    return total


async def ensure_tagger_auto_run(config: ChatImageConfig) -> None:
    global auto_run_task
    async with AUTO_RUN_LOCK:
        if auto_run_task is not None and not auto_run_task.done():
            return
        auto_run_task = asyncio.create_task(_auto_run_worker(config))


async def _auto_run_worker(config: ChatImageConfig) -> None:
    while True:
        summary = await run_tagger_once(config)
        if summary["picked"] == 0:
            return
        logger.info(
            "Tagger auto-run batch done: picked={} success={} failed={} requeued={}",
            summary["picked"],
            summary["success"],
            summary["failed"],
            summary["requeued"],
        )


def _record_queue_metrics(*, outcome: str, depth: int) -> None:
    attributes = {"outcome": outcome}
    if QUEUE_ENQUEUE_COUNTER is not None:
        QUEUE_ENQUEUE_COUNTER.add(1, attributes)
    if QUEUE_DEPTH_HIST is not None:
        QUEUE_DEPTH_HIST.record(max(0, depth), attributes)


def _record_batch_metrics(*, summary: dict[str, int], started_at: float) -> None:
    picked = max(0, summary.get("picked", 0))
    success = max(0, summary.get("success", 0))
    failed = max(0, summary.get("failed", 0))
    requeued = max(0, summary.get("requeued", 0))

    if TAGGER_BATCH_COUNTER is not None:
        TAGGER_BATCH_COUNTER.add(1, {"outcome": "completed"})
    if TAGGER_ITEM_COUNTER is not None:
        if picked:
            TAGGER_ITEM_COUNTER.add(picked, {"outcome": "picked"})
        if success:
            TAGGER_ITEM_COUNTER.add(success, {"outcome": "success"})
        if failed:
            TAGGER_ITEM_COUNTER.add(failed, {"outcome": "failed"})
        if requeued:
            TAGGER_ITEM_COUNTER.add(requeued, {"outcome": "requeued"})
    if TAGGER_BATCH_LATENCY_MS is not None:
        latency_ms = max(0.0, (time.perf_counter() - started_at) * 1000.0)
        TAGGER_BATCH_LATENCY_MS.record(latency_ms, {"outcome": "completed"})
