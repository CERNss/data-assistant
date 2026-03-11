from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


TASK_VERSION = 2


@dataclass(frozen=True)
class TaskV2:
    version: int
    image_id: int
    sha256: str
    source_url: str
    original_url: str
    context: dict[str, Any]
    image_path: str | None = None


def is_v1_payload(payload: dict[str, Any]) -> bool:
    return "version" not in payload and isinstance(payload.get("image_path"), str)


def encode_task(task: TaskV2) -> bytes:
    payload: dict[str, Any] = {
        "version": max(TASK_VERSION, int(task.version)),
        "image_id": task.image_id,
        "sha256": task.sha256,
        "source_url": task.source_url,
        "original_url": task.original_url,
        "context": task.context,
    }
    if task.image_path:
        payload["image_path"] = task.image_path
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def decode_task(data: bytes) -> TaskV2:
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")

    if is_v1_payload(payload):
        return _decode_v1_payload(payload)
    return _decode_v2_payload(payload)


def _decode_v2_payload(payload: dict[str, Any]) -> TaskV2:
    version_raw = payload.get("version")
    image_id_raw = payload.get("image_id")
    sha256_raw = payload.get("sha256")
    source_url_raw = payload.get("source_url")
    original_url_raw = payload.get("original_url")
    context_raw = payload.get("context")
    image_path_raw = payload.get("image_path")

    if not isinstance(version_raw, int) or version_raw < TASK_VERSION:
        raise ValueError("payload.version is invalid")
    if not isinstance(image_id_raw, int) or image_id_raw <= 0:
        raise ValueError("payload.image_id is invalid")
    if not isinstance(sha256_raw, str) or not sha256_raw.strip():
        raise ValueError("payload.sha256 is empty")
    if not isinstance(source_url_raw, str):
        raise ValueError("payload.source_url is invalid")
    if not isinstance(original_url_raw, str):
        raise ValueError("payload.original_url is invalid")
    if not isinstance(context_raw, dict):
        raise ValueError("payload.context is not an object")
    if image_path_raw is not None and not isinstance(image_path_raw, str):
        raise ValueError("payload.image_path is invalid")

    return TaskV2(
        version=version_raw,
        image_id=image_id_raw,
        sha256=sha256_raw.strip(),
        source_url=source_url_raw,
        original_url=original_url_raw,
        context=context_raw,
        image_path=image_path_raw.strip() if isinstance(image_path_raw, str) else None,
    )


def _decode_v1_payload(payload: dict[str, Any]) -> TaskV2:
    image_path_raw = payload.get("image_path")
    context_raw = payload.get("context")

    if not isinstance(image_path_raw, str) or not image_path_raw.strip():
        raise ValueError("payload.image_path is empty")
    if not isinstance(context_raw, dict):
        raise ValueError("payload.context is not an object")

    image_id = _coerce_positive_int(context_raw.get("image_id"), "context.image_id")
    source_url = _coerce_str(context_raw.get("source_url"), default="")
    original_url = _coerce_str(context_raw.get("original_url"), default=source_url)
    sha256 = _coerce_str(context_raw.get("hash_sha256"), default="")

    return TaskV2(
        version=1,
        image_id=image_id,
        sha256=sha256,
        source_url=source_url,
        original_url=original_url,
        context=context_raw,
        image_path=image_path_raw.strip(),
    )


def _coerce_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} is invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} is invalid") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} is invalid")
    return parsed


def _coerce_str(value: Any, *, default: str) -> str:
    if isinstance(value, str):
        return value
    return default
