from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from nonebot import logger
from opentelemetry import trace

from .audit import append_json_line
from .config import ChatImageConfig


TRACER = trace.get_tracer("data_logger.plugins.chat_image.tagger_pipeline")
QUEUE_LOCK = asyncio.Lock()
AUTO_RUN_LOCK = asyncio.Lock()
AUTO_RUN_TASK: asyncio.Task[None] | None = None

BatchItem = dict[str, Any]
BatchResult = dict[str, Any]
TaggerRunner = Callable[[ChatImageConfig, list[BatchItem]], Awaitable[list[BatchResult]]]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_queue(queue_file: Path) -> list[BatchItem]:
    if not queue_file.exists():
        return []
    try:
        payload = json.loads(queue_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid tagger queue file: {}", queue_file)
        return []
    if not isinstance(payload, list):
        logger.warning("Unexpected tagger queue payload type: {}", queue_file)
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


def _resolve_tool_path(tool_root: Path, value: Path) -> Path:
    if value.is_absolute():
        return value
    return (tool_root / value).resolve()


def _build_tagger_command(config: ChatImageConfig, image_list_path: Path) -> list[str]:
    tagger = config.tagger
    if tagger.tool_root is None:
        raise RuntimeError("CHAT_IMAGE_TAGGER_TOOL_ROOT is not configured")
    entry_script = _resolve_tool_path(tagger.tool_root, tagger.entry_script)
    cmd = [tagger.python_bin, str(entry_script), "--image_list", str(image_list_path)]
    if tagger.config_file is not None:
        cmd.extend(["--config", str(_resolve_tool_path(tagger.tool_root, tagger.config_file))])
    return cmd


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.hardlink_to(source)
    except OSError:
        shutil.copy2(source, target)


def _run_subprocess(cmd: list[str], cwd: Path, timeout_sec: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        input="\n",
        capture_output=True,
        timeout=timeout_sec,
        check=False,
    )


async def _run_external_tagger_batch(
    config: ChatImageConfig, batch_items: list[BatchItem]
) -> list[BatchResult]:
    tagger = config.tagger
    if tagger.tool_root is None:
        raise RuntimeError("CHAT_IMAGE_TAGGER_TOOL_ROOT is empty")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    run_dir = tagger.run_root / run_id
    stage_root = run_dir / "stage"
    image_list_path = run_dir / "image_list.txt"
    stage_root.mkdir(parents=True, exist_ok=True)

    pre_failures: list[BatchResult] = []
    staged: list[tuple[BatchItem, Path]] = []

    for idx, item in enumerate(batch_items):
        source_path = Path(str(item.get("image_path", "")))
        if not source_path.exists():
            pre_failures.append(
                {
                    "item": item,
                    "status": "failed",
                    "error": f"image not found: {source_path}",
                }
            )
            continue
        stage_dir = stage_root / f"{idx:05d}.info"
        stage_name = source_path.name or f"image_{idx}{source_path.suffix or '.bin'}"
        stage_image = stage_dir / stage_name
        _link_or_copy(source_path, stage_image)
        staged.append((item, stage_image))

    if not staged:
        return pre_failures

    image_list_path.write_text(
        "\n".join(str(stage_image.resolve()) for _, stage_image in staged) + "\n",
        encoding="utf-8",
    )

    cmd = _build_tagger_command(config, image_list_path)
    result_list: list[BatchResult] = []
    try:
        completed = await asyncio.to_thread(_run_subprocess, cmd, tagger.tool_root, tagger.timeout_sec)
        if completed.returncode != 0:
            message = (
                f"tagger exited with code {completed.returncode}. "
                f"stdout={_tail_text(completed.stdout)} stderr={_tail_text(completed.stderr)}"
            )
            raise RuntimeError(message)

        for item, stage_image in staged:
            metadata_file = stage_image.parent / "metadata.json"
            if not metadata_file.exists():
                result_list.append(
                    {
                        "item": item,
                        "status": "failed",
                        "error": f"metadata missing: {metadata_file}",
                    }
                )
                continue

            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                result_list.append(
                    {
                        "item": item,
                        "status": "failed",
                        "error": f"invalid metadata JSON: {exc}",
                    }
                )
                continue

            raw_tags = metadata.get("tags", [])
            if not isinstance(raw_tags, list):
                result_list.append(
                    {
                        "item": item,
                        "status": "failed",
                        "error": "metadata.tags is not a list",
                    }
                )
                continue
            tags = [str(tag) for tag in raw_tags if str(tag).strip()]
            result_list.append(
                {
                    "item": item,
                    "status": "success",
                    "tags": tags,
                }
            )
    finally:
        if not tagger.keep_run_artifacts and run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)

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
    if tagger.tool_root is None:
        logger.warning("Tagger is enabled but CHAT_IMAGE_TAGGER_TOOL_ROOT is not configured")
        return

    queued_image_path = str(image_path.resolve())
    queue_item = {
        "image_path": queued_image_path,
        "context": context,
        "enqueued_at": _utc_now_iso(),
        "attempt_count": 0,
    }

    async with QUEUE_LOCK:
        queue_items = _load_queue(tagger.queue_file)
        if any(item.get("image_path") == queued_image_path for item in queue_items):
            return
        queue_items.append(queue_item)
        _save_queue(tagger.queue_file, queue_items)

    logger.info("Queued image for tagging: path={}", queued_image_path)
    if tagger.auto_run:
        await ensure_tagger_auto_run(config)


def get_pending_tagger_count(config: ChatImageConfig) -> int:
    if not config.tagger.enabled:
        return 0
    return len(_load_queue(config.tagger.queue_file))


async def run_tagger_once(
    config: ChatImageConfig, *, runner: TaggerRunner | None = None
) -> dict[str, int]:
    tagger = config.tagger
    summary = {"picked": 0, "success": 0, "failed": 0, "requeued": 0}
    if not tagger.enabled or tagger.tool_root is None:
        return summary

    async with QUEUE_LOCK:
        queue_items = _load_queue(tagger.queue_file)
        if not queue_items:
            return summary
        batch_items = queue_items[: tagger.batch_size]
        queue_items = queue_items[tagger.batch_size :]
        _save_queue(tagger.queue_file, queue_items)
    summary["picked"] = len(batch_items)

    runner_impl = runner or _run_external_tagger_batch
    with TRACER.start_as_current_span(
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
    global AUTO_RUN_TASK
    async with AUTO_RUN_LOCK:
        if AUTO_RUN_TASK is not None and not AUTO_RUN_TASK.done():
            return
        AUTO_RUN_TASK = asyncio.create_task(_auto_run_worker(config))


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
