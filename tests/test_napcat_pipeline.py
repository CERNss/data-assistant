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

from plugins.napcat.config import NapCatConfig
from plugins.napcat.event import ImageSegment, OneBotEvent
from plugins.napcat.pipeline import _derive_stream_state, _process_image


def _napcat_config() -> NapCatConfig:
    return NapCatConfig(
        ws_host="0.0.0.0",
        ws_port=3001,
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
                    "plugins.persistence.repository.insert_image",
                    new_callable=AsyncMock,
                ) as mock_insert_image,
                patch(
                    "plugins.persistence.repository.update_image_download_failure",
                    new_callable=AsyncMock,
                ) as mock_update_failure,
                patch("plugins.chat_image.audit.append_json_line") as mock_append,
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


if __name__ == "__main__":
    unittest.main()
