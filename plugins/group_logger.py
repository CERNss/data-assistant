from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from nonebot import logger, on_type
from nonebot.adapters import Bot
from nonebot.adapters.qq.event import (
    GroupAtMessageCreateEvent,
    GroupMsgReceiveEvent,
    GroupMsgRejectEvent,
)


LOG_DIR = Path("data")
MESSAGE_LOG_FILE = LOG_DIR / "group_messages.jsonl"
NOTICE_LOG_FILE = LOG_DIR / "group_notices.jsonl"
IMAGE_LOG_FILE = LOG_DIR / "group_images.jsonl"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"}
IMAGE_SAVE_ROOT = Path(os.getenv("GROUP_IMAGE_SAVE_DIR", "data/group_images"))
IMAGE_TIMEOUT_SEC = float(os.getenv("GROUP_IMAGE_TIMEOUT_SEC", "20"))


def _append_json_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False))
        fp.write("\n")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or "image.bin"


def _is_image_attachment(content_type: str | None, filename: str | None, url: str | None) -> bool:
    if content_type and content_type.lower().startswith("image/"):
        return True
    if filename and Path(filename).suffix.lower() in IMAGE_EXTENSIONS:
        return True
    if url:
        path = Path(urlparse(url).path)
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return True
    return False


def _choose_filename(filename: str | None, fallback_index: int, url: str | None) -> str:
    if filename:
        return _safe_filename(filename)
    if url:
        parsed_name = Path(urlparse(url).path).name
        if parsed_name:
            return _safe_filename(parsed_name)
    return f"image_{fallback_index}.bin"


async def _download_image_bytes(url: str) -> bytes:
    timeout = aiohttp.ClientTimeout(total=IMAGE_TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()


group_message_logger = on_type(GroupAtMessageCreateEvent, priority=1, block=False)
group_receive_notice_logger = on_type(GroupMsgReceiveEvent, priority=1, block=False)
group_reject_notice_logger = on_type(GroupMsgRejectEvent, priority=1, block=False)


@group_message_logger.handle()
async def handle_group_message(bot: Bot, event: GroupAtMessageCreateEvent) -> None:
    payload = {
        "logged_at": datetime.now(UTC).isoformat(),
        "self_id": bot.self_id,
        "event_name": event.get_event_name(),
        "event_description": event.get_event_description(),
        "group_openid": event.group_openid,
        "user_id": event.get_user_id(),
        "message_id": event.id,
        "plain_text": event.get_plaintext(),
        "message": str(event.get_message()),
        "raw_event": event.model_dump(mode="json"),
    }
    _append_json_line(MESSAGE_LOG_FILE, payload)
    logger.info(
        "Logged group message: group_openid={} user_id={} message_id={}",
        event.group_openid,
        event.get_user_id(),
        event.id,
    )

    day = datetime.now(UTC).strftime("%Y-%m-%d")
    image_dir = IMAGE_SAVE_ROOT / day / event.group_openid
    for idx, attachment in enumerate(event.attachments or []):
        source_url = attachment.url
        if not source_url or not _is_image_attachment(
            attachment.content_type, attachment.filename, source_url
        ):
            continue

        entry_base = {
            "logged_at": datetime.now(UTC).isoformat(),
            "self_id": bot.self_id,
            "event_name": event.get_event_name(),
            "group_openid": event.group_openid,
            "user_id": event.get_user_id(),
            "message_id": event.id,
            "attachment_index": idx,
            "source_url": source_url,
            "attachment": attachment.model_dump(mode="json"),
        }
        try:
            raw_bytes = await _download_image_bytes(source_url)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            original_name = _choose_filename(attachment.filename, idx, source_url)
            saved_name = f"{ts}_{event.id}_{idx}_{original_name}"
            save_path = image_dir / saved_name
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(raw_bytes)

            _append_json_line(
                IMAGE_LOG_FILE,
                {
                    **entry_base,
                    "status": "success",
                    "saved_path": str(save_path),
                    "size": len(raw_bytes),
                },
            )
            logger.info("Saved group image: path={} size={}", save_path, len(raw_bytes))
        except Exception as exc:
            _append_json_line(
                IMAGE_LOG_FILE,
                {**entry_base, "status": "failed", "error": str(exc)},
            )
            logger.warning("Failed to save group image: url={} error={}", source_url, exc)


@group_receive_notice_logger.handle()
async def handle_group_receive_notice(bot: Bot, event: GroupMsgReceiveEvent) -> None:
    payload = {
        "logged_at": datetime.now(UTC).isoformat(),
        "self_id": bot.self_id,
        "event_name": event.get_event_name(),
        "event_description": event.get_event_description(),
        "group_openid": event.group_openid,
        "operator_openid": event.op_member_openid,
        "raw_event": event.model_dump(mode="json"),
    }
    _append_json_line(NOTICE_LOG_FILE, payload)
    logger.info(
        "Logged group receive notice: group_openid={} operator_openid={}",
        event.group_openid,
        event.op_member_openid,
    )


@group_reject_notice_logger.handle()
async def handle_group_reject_notice(bot: Bot, event: GroupMsgRejectEvent) -> None:
    payload = {
        "logged_at": datetime.now(UTC).isoformat(),
        "self_id": bot.self_id,
        "event_name": event.get_event_name(),
        "event_description": event.get_event_description(),
        "group_openid": event.group_openid,
        "operator_openid": event.op_member_openid,
        "raw_event": event.model_dump(mode="json"),
    }
    _append_json_line(NOTICE_LOG_FILE, payload)
    logger.info(
        "Logged group reject notice: group_openid={} operator_openid={}",
        event.group_openid,
        event.op_member_openid,
    )
