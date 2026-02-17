from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def _append_json_line(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False))
        fp.write("\n")


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
