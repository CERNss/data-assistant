from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from nonebot import logger
from nonebot.adapters import Bot
from opentelemetry import trace

from .audit import append_json_line
from .config import load_chat_image_config
from .downloader import download_image_bytes_with_retry
from .nats_task_bus import publish_tagger_task
from .storage import build_image_save_path, is_image_attachment
from .tagger_pipeline import enqueue_image_for_tagging, enqueue_tagger_task_payload


TRACER = trace.get_tracer("data_assistant.plugins.chat_image.service")


async def save_message_images(
    *,
    bot: Bot,
    event_name: str,
    chat_type: str,
    chat_id: str,
    message_id: str,
    user_id: str,
    attachments: list[Any] | None,
) -> None:
    config = load_chat_image_config()
    with TRACER.start_as_current_span(
        "chat_image.save_batch",
        attributes={
            "chat.type": chat_type,
            "chat.id": chat_id,
            "chat.message_id": message_id,
            "chat.attachments_count": len(attachments or []),
        },
    ):
        for idx, attachment in enumerate(attachments or []):
            source_url = attachment.url
            if not source_url or not is_image_attachment(
                attachment.content_type, attachment.filename, source_url
            ):
                continue

            entry_base = {
                "logged_at": datetime.now(UTC).isoformat(),
                "self_id": bot.self_id,
                "event_name": event_name,
                "chat_type": chat_type,
                "chat_id": chat_id,
                "user_id": user_id,
                "message_id": message_id,
                "attachment_index": idx,
                "source_url": source_url,
                "attachment": attachment.model_dump(mode="json"),
            }
            try:
                raw_bytes, attempt_count = await download_image_bytes_with_retry(source_url, config)
                save_path = build_image_save_path(
                    save_root=config.save_root,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    message_id=message_id,
                    attachment_index=idx,
                    filename=attachment.filename,
                    source_url=source_url,
                )
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(raw_bytes)

                append_json_line(
                    config.audit_log_file,
                    {
                        **entry_base,
                        "status": "success",
                        "saved_path": str(save_path),
                        "size": len(raw_bytes),
                        "attempt_count": attempt_count,
                    },
                )
                logger.info(
                    "Saved chat image: chat_type={} chat_id={} path={} size={}",
                    chat_type,
                    chat_id,
                    save_path,
                    len(raw_bytes),
                )
                tag_context = {
                    "event_name": event_name,
                    "chat_type": chat_type,
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "message_id": message_id,
                    "attachment_index": idx,
                    "source_url": source_url,
                }

                published = await publish_tagger_task(
                    config,
                    image_path=save_path,
                    context=tag_context,
                )
                if not published:
                    if config.nats.enabled and config.nats.fallback_to_local_queue:
                        await enqueue_tagger_task_payload(
                            config=config,
                            payload={
                                "image_path": str(save_path),
                                "context": tag_context,
                            },
                        )
                    elif not config.nats.enabled:
                        await enqueue_image_for_tagging(
                            config=config,
                            image_path=save_path,
                            context=tag_context,
                        )
            except Exception as exc:
                append_json_line(
                    config.audit_log_file,
                    {
                        **entry_base,
                        "status": "failed",
                        "error": str(exc),
                        "attempt_count": max(1, config.retry_count),
                    },
                )
                logger.warning(
                    "Failed to save chat image: chat_type={} chat_id={} url={} error={}",
                    chat_type,
                    chat_id,
                    source_url,
                    exc,
                )
