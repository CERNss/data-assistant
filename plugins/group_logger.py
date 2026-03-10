from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from nonebot import logger, on_type
from nonebot.adapters import Bot
from nonebot.adapters.qq.event import (
    C2CMessageCreateEvent,
    GroupAtMessageCreateEvent,
    GroupMsgReceiveEvent,
    GroupMsgRejectEvent,
)
from opentelemetry import trace

from .chat_image.audit import append_json_line
from .chat_image.service import save_message_images

LOG_DIR = Path("data")
MESSAGE_LOG_FILE = LOG_DIR / "group_messages.jsonl"
NOTICE_LOG_FILE = LOG_DIR / "group_notices.jsonl"
TRACER = trace.get_tracer("data_assistant.plugins.group_logger")


group_message_logger = on_type(GroupAtMessageCreateEvent, priority=1, block=False)
c2c_message_logger = on_type(C2CMessageCreateEvent, priority=1, block=False)
group_receive_notice_logger = on_type(GroupMsgReceiveEvent, priority=1, block=False)
group_reject_notice_logger = on_type(GroupMsgRejectEvent, priority=1, block=False)


@group_message_logger.handle()
async def handle_group_message(bot: Bot, event: GroupAtMessageCreateEvent) -> None:
    with TRACER.start_as_current_span(
        "qq.group_message.handle",
        attributes={
            "chat.type": "group",
            "chat.id": event.group_openid,
            "chat.message_id": event.id,
            "chat.user_id": event.get_user_id(),
        },
    ):
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
        append_json_line(MESSAGE_LOG_FILE, payload)
        logger.info(
            "Logged group message: group_openid={} user_id={} message_id={}",
            event.group_openid,
            event.get_user_id(),
            event.id,
        )

        await save_message_images(
            bot=bot,
            event_name=event.get_event_name(),
            chat_type="group",
            chat_id=event.group_openid,
            message_id=event.id,
            user_id=event.get_user_id(),
            attachments=event.attachments,
        )


@c2c_message_logger.handle()
async def handle_c2c_message(bot: Bot, event: C2CMessageCreateEvent) -> None:
    with TRACER.start_as_current_span(
        "qq.private_message.handle",
        attributes={
            "chat.type": "private",
            "chat.id": event.get_user_id(),
            "chat.message_id": event.id,
            "chat.user_id": event.get_user_id(),
        },
    ):
        await save_message_images(
            bot=bot,
            event_name=event.get_event_name(),
            chat_type="private",
            chat_id=event.get_user_id(),
            message_id=event.id,
            user_id=event.get_user_id(),
            attachments=event.attachments,
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
    append_json_line(NOTICE_LOG_FILE, payload)
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
    append_json_line(NOTICE_LOG_FILE, payload)
    logger.info(
        "Logged group reject notice: group_openid={} operator_openid={}",
        event.group_openid,
        event.op_member_openid,
    )
