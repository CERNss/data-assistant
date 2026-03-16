from __future__ import annotations

import tempfile
import unittest
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

if "asyncpg" not in sys.modules:
    _asyncpg_stub = types.ModuleType("asyncpg")
    setattr(_asyncpg_stub, "Pool", object)
    setattr(_asyncpg_stub, "Connection", object)
    setattr(_asyncpg_stub, "create_pool", MagicMock())
    sys.modules["asyncpg"] = _asyncpg_stub

from logger_service.service.napcat.config import NapCatConfig
from logger_service.service.napcat.event import ImageSegment, OneBotEvent
from logger_service.service.napcat.pipeline import (
    _derive_stream_state,
    _process_image,
    persist_event,
)


def _napcat_config() -> NapCatConfig:
    return NapCatConfig(
        ws_host="0.0.0.0",
        ws_port=8082,
        ws_path="/onebot/v11/ws",
        token="",
        action_timeout_sec=8.0,
        reconnect_sec=5.0,
        heartbeat_timeout_sec=60.0,
        bot_qq=0,
    )


def _event_with_image(image: ImageSegment) -> OneBotEvent:
    return OneBotEvent(
        post_type="message",
        time=1700000000,
        self_id=3755597070,
        message_type="group",
        sub_type="normal",
        message_id="100",
        user_id=1,
        group_id=2,
        group_name="g",
        raw_message="[image]",
        message_segments=None,
        message_cq=None,
        sender=None,
        images=[image],
        raw={"post_type": "message"},
    )


class TestStreamStateDerivation(unittest.TestCase):
    def test_derive_stream_mode_from_segment_data(self) -> None:
        image = ImageSegment(
            seq=0,
            url_raw="https://example.com/a.jpg",
            url_decoded="https://example.com/a.jpg",
            file_name="a.image",
            sub_type="0",
            file_size=1,
            summary="[图片]",
            raw_segment={
                "type": "image",
                "data": {"type": "stream", "data_type": "data_chunk"},
            },
        )

        transfer_mode, stream_phase, stream_data_type = _derive_stream_state(image)

        self.assertEqual(transfer_mode, "stream")
        self.assertEqual(stream_phase, "stream")
        self.assertEqual(stream_data_type, "data_chunk")


class TestProcessImageMissingUrl(unittest.IsolatedAsyncioTestCase):
    async def test_missing_url_still_inserts_row_and_marks_failed(self) -> None:
        image = ImageSegment(
            seq=0,
            url_raw=None,
            url_decoded=None,
            file_name="missing.image",
            sub_type=None,
            file_size=None,
            summary=None,
            raw_segment={"type": "image", "data": {}},
        )
        event = _event_with_image(image)

        with tempfile.TemporaryDirectory() as tmp:
            chat_config = SimpleNamespace(
                audit_log_file=Path(tmp) / "audit.jsonl",
                nats=SimpleNamespace(
                    enabled=False, fallback_to_local_queue=True, subject="t"
                ),
                retry_count=3,
                save_root=Path(tmp),
            )

            with (
                patch(
                    "logger_service.service.persistence.repository.insert_image",
                    new_callable=AsyncMock,
                ) as mock_insert_image,
                patch(
                    "logger_service.service.persistence.repository.update_image_download_failure",
                    new_callable=AsyncMock,
                ) as mock_update_failure,
                patch(
                    "logger_service.service.chat_image.audit.append_json_line"
                ) as mock_append,
            ):
                mock_insert_image.return_value = 42

                await _process_image(
                    event_id=10,
                    event=event,
                    image=image,
                    chat_config=chat_config,
                    napcat_config=_napcat_config(),
                )

            mock_insert_image.assert_awaited_once()
            mock_update_failure.assert_awaited_once()
            await_args = mock_update_failure.await_args
            self.assertIsNotNone(await_args)
            assert await_args is not None
            self.assertEqual(await_args.args[0], 42)
            self.assertEqual(
                await_args.kwargs["error"],
                "missing_image_url",
            )
            mock_append.assert_called_once()


def _base_event(
    *,
    post_type: str,
    message_type: str | None,
    user_id: int | None,
    group_id: int | None,
    sender: dict[str, object] | None,
    images: list[ImageSegment] | None = None,
) -> OneBotEvent:
    return OneBotEvent(
        post_type=post_type,
        time=1700000000,
        self_id=3755597070,
        message_type=message_type,
        sub_type="normal",
        message_id="msg-1",
        user_id=user_id,
        group_id=group_id,
        group_name="group-name" if group_id is not None else None,
        raw_message="hello",
        message_segments=[
            {"type": "text", "data": {"text": "hello "}},
            {"type": "text", "data": {"text": "world"}},
        ],
        message_cq=None,
        sender=sender,
        images=images or [],
        raw={"post_type": post_type},
    )


class TestPersistEventStructuredMessage(unittest.IsolatedAsyncioTestCase):
    async def test_group_message_persists_expected_fields(self) -> None:
        event = _base_event(
            post_type="message",
            message_type="group",
            user_id=10001,
            group_id=20002,
            sender={"nickname": "nick", "card": "card", "role": "admin"},
        )

        with (
            patch(
                "logger_service.service.persistence.repository.insert_event",
                new_callable=AsyncMock,
            ) as mock_insert_event,
            patch(
                "logger_service.service.persistence.repository.insert_message",
                new_callable=AsyncMock,
            ) as mock_insert_message,
            patch(
                "logger_service.service.chat_image.config.load_chat_image_config",
                return_value=SimpleNamespace(),
            ),
            patch(
                "logger_service.service.napcat.pipeline.load_napcat_config",
                return_value=_napcat_config(),
            ),
        ):
            mock_insert_event.return_value = 1
            await persist_event(event)

        mock_insert_message.assert_awaited_once()
        await_args = mock_insert_message.await_args
        self.assertIsNotNone(await_args)
        assert await_args is not None
        kwargs = await_args.kwargs
        self.assertEqual(kwargs["message_type"], "group")
        self.assertEqual(kwargs["user_id"], 10001)
        self.assertEqual(kwargs["group_id"], 20002)
        self.assertEqual(kwargs["sender_nickname"], "nick")
        self.assertEqual(kwargs["sender_card"], "card")
        self.assertEqual(kwargs["sender_role"], "admin")
        self.assertEqual(kwargs["plain_text"], "hello world")

    async def test_private_message_sets_sender_card_role_none(self) -> None:
        event = _base_event(
            post_type="message",
            message_type="private",
            user_id=10001,
            group_id=None,
            sender={"nickname": "nick", "card": "card", "role": "member"},
        )

        with (
            patch(
                "logger_service.service.persistence.repository.insert_event",
                new_callable=AsyncMock,
            ) as mock_insert_event,
            patch(
                "logger_service.service.persistence.repository.insert_message",
                new_callable=AsyncMock,
            ) as mock_insert_message,
            patch(
                "logger_service.service.chat_image.config.load_chat_image_config",
                return_value=SimpleNamespace(),
            ),
            patch(
                "logger_service.service.napcat.pipeline.load_napcat_config",
                return_value=_napcat_config(),
            ),
        ):
            mock_insert_event.return_value = 2
            await persist_event(event)

        await_args = mock_insert_message.await_args
        self.assertIsNotNone(await_args)
        assert await_args is not None
        kwargs = await_args.kwargs
        self.assertIsNone(kwargs["group_id"])
        self.assertIsNone(kwargs["sender_card"])
        self.assertIsNone(kwargs["sender_role"])

    async def test_message_sent_uses_self_id_as_user_id(self) -> None:
        event = _base_event(
            post_type="message_sent",
            message_type="group",
            user_id=999,
            group_id=20002,
            sender={"nickname": "bot"},
        )

        with (
            patch(
                "logger_service.service.persistence.repository.insert_event",
                new_callable=AsyncMock,
            ) as mock_insert_event,
            patch(
                "logger_service.service.persistence.repository.insert_message",
                new_callable=AsyncMock,
            ) as mock_insert_message,
            patch(
                "logger_service.service.chat_image.config.load_chat_image_config",
                return_value=SimpleNamespace(),
            ),
            patch(
                "logger_service.service.napcat.pipeline.load_napcat_config",
                return_value=_napcat_config(),
            ),
        ):
            mock_insert_event.return_value = 3
            await persist_event(event)

        await_args = mock_insert_message.await_args
        self.assertIsNotNone(await_args)
        assert await_args is not None
        kwargs = await_args.kwargs
        self.assertEqual(kwargs["user_id"], event.self_id)

    async def test_non_message_event_does_not_insert_structured_message(self) -> None:
        event = _base_event(
            post_type="notice",
            message_type=None,
            user_id=None,
            group_id=None,
            sender=None,
        )

        with (
            patch(
                "logger_service.service.persistence.repository.insert_event",
                new_callable=AsyncMock,
            ) as mock_insert_event,
            patch(
                "logger_service.service.persistence.repository.insert_message",
                new_callable=AsyncMock,
            ) as mock_insert_message,
            patch(
                "logger_service.service.chat_image.config.load_chat_image_config",
                return_value=SimpleNamespace(),
            ),
            patch(
                "logger_service.service.napcat.pipeline.load_napcat_config",
                return_value=_napcat_config(),
            ),
        ):
            mock_insert_event.return_value = 4
            await persist_event(event)

        mock_insert_message.assert_not_awaited()

    async def test_insert_message_failure_logs_and_continues_image_processing(
        self,
    ) -> None:
        image = ImageSegment(
            seq=0,
            url_raw="https://example.com/a.jpg",
            url_decoded="https://example.com/a.jpg",
            file_name="a.jpg",
            sub_type=None,
            file_size=None,
            summary=None,
            raw_segment={"type": "image", "data": {"url": "https://example.com/a.jpg"}},
        )
        event = _base_event(
            post_type="message",
            message_type="group",
            user_id=10001,
            group_id=20002,
            sender={"nickname": "nick"},
            images=[image],
        )

        with (
            patch(
                "logger_service.service.persistence.repository.insert_event",
                new_callable=AsyncMock,
            ) as mock_insert_event,
            patch(
                "logger_service.service.persistence.repository.insert_message",
                new_callable=AsyncMock,
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "logger_service.service.napcat.pipeline._process_image",
                new_callable=AsyncMock,
            ) as mock_process_image,
            patch(
                "logger_service.service.chat_image.config.load_chat_image_config",
                return_value=SimpleNamespace(),
            ),
            patch(
                "logger_service.service.napcat.pipeline.load_napcat_config",
                return_value=_napcat_config(),
            ),
            patch(
                "logger_service.service.napcat.pipeline.logger.error"
            ) as mock_log_error,
        ):
            mock_insert_event.return_value = 5
            await persist_event(event)

        mock_log_error.assert_called()
        mock_process_image.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
