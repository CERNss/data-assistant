from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from logger_service.service.chat_image.config import (
    ChatImageConfig,
    NatsTaskBusConfig,
)


class TestChatImageNatsPublisher(unittest.IsolatedAsyncioTestCase):
    def _build_config(self, *, jetstream_enabled: bool = True) -> ChatImageConfig:
        return ChatImageConfig(
            save_root=Path("data/chat_images"),
            timeout_sec=20.0,
            retry_count=3,
            retry_delay_sec=0.8,
            audit_log_file=Path("data/group_images.jsonl"),
            nats=NatsTaskBusConfig(
                enabled=True,
                servers=("nats://127.0.0.1:4222",),
                subject="chat.image.tagger.task",
                client_name="data-assistant",
                connect_timeout_sec=5.0,
                publish_timeout_sec=3.0,
                jetstream_enabled=jetstream_enabled,
                stream_name="CHAT_IMAGE_TAGGER_TASKS",
                stream_subjects=("chat.image.tagger.task",),
            ),
        )

    def setUp(self) -> None:
        from logger_service.service.chat_image import nats_publisher

        nats_publisher._nats_client = None
        nats_publisher._jetstream_context = None
        nats_publisher._ensured_streams = set()

    def _fake_nats_api_modules(self) -> dict[str, types.ModuleType]:
        class RetentionPolicy:
            LIMITS = "limits"

        class StorageType:
            FILE = "file"

        class StreamConfig:
            def __init__(self, **kwargs: object) -> None:
                self.__dict__.update(kwargs)

        api_module = types.ModuleType("nats.js.api")
        api_module.RetentionPolicy = RetentionPolicy
        api_module.StorageType = StorageType
        api_module.StreamConfig = StreamConfig
        return {
            "nats": types.ModuleType("nats"),
            "nats.js": types.ModuleType("nats.js"),
            "nats.js.api": api_module,
        }

    async def test_publish_uses_jetstream_and_requires_pub_ack(self) -> None:
        config = self._build_config(jetstream_enabled=True)
        js = SimpleNamespace(
            stream_info=AsyncMock(
                return_value=SimpleNamespace(
                    config=SimpleNamespace(subjects=["chat.image.tagger.task"])
                )
            ),
            add_stream=AsyncMock(),
            update_stream=AsyncMock(),
            publish=AsyncMock(return_value=object()),
        )
        client = SimpleNamespace(jetstream=lambda: js)

        with (
            patch.dict(sys.modules, self._fake_nats_api_modules()),
            patch(
                "logger_service.service.chat_image.nats_publisher._get_or_connect_nats",
                new=AsyncMock(return_value=client),
            ),
        ):
            from logger_service.service.chat_image.nats_publisher import (
                publish_tagger_task_with_result,
            )

            ok, error = await publish_tagger_task_with_result(
                config,
                payload={"image_id": 1, "context": {"message_id": "m1"}},
            )

        self.assertTrue(ok)
        self.assertIsNone(error)
        js.stream_info.assert_awaited_once_with("CHAT_IMAGE_TAGGER_TASKS")
        js.add_stream.assert_not_awaited()
        js.publish.assert_awaited_once()
        args, kwargs = js.publish.await_args
        self.assertEqual(args[0], "chat.image.tagger.task")
        self.assertEqual(kwargs["timeout"], 3.0)
        self.assertEqual(kwargs["stream"], "CHAT_IMAGE_TAGGER_TASKS")

    async def test_publish_core_fallback_flushes_client(self) -> None:
        config = self._build_config(jetstream_enabled=False)
        client = SimpleNamespace(
            publish=AsyncMock(),
            flush=AsyncMock(),
            jetstream=lambda: self.fail("core publish must not create JetStream"),
        )

        with patch(
            "logger_service.service.chat_image.nats_publisher._get_or_connect_nats",
            new=AsyncMock(return_value=client),
        ):
            from logger_service.service.chat_image.nats_publisher import (
                publish_tagger_task_with_result,
            )

            ok, error = await publish_tagger_task_with_result(
                config,
                payload={"image_id": 1, "context": {"message_id": "m1"}},
            )

        self.assertTrue(ok)
        self.assertIsNone(error)
        client.publish.assert_awaited_once()
        client.flush.assert_awaited_once_with(timeout=3.0)

    async def test_ensure_stream_adds_missing_stream(self) -> None:
        config = self._build_config(jetstream_enabled=True)

        class RetentionPolicy:
            LIMITS = "limits"

        class StorageType:
            FILE = "file"

        class StreamConfig:
            def __init__(self, **kwargs: object) -> None:
                self.__dict__.update(kwargs)

        api_module = types.ModuleType("nats.js.api")
        api_module.RetentionPolicy = RetentionPolicy
        api_module.StorageType = StorageType
        api_module.StreamConfig = StreamConfig
        js = SimpleNamespace(
            stream_info=AsyncMock(side_effect=RuntimeError("not found")),
            add_stream=AsyncMock(),
            update_stream=AsyncMock(),
        )
        with patch.dict(
            sys.modules,
            {
                "nats": types.ModuleType("nats"),
                "nats.js": types.ModuleType("nats.js"),
                "nats.js.api": api_module,
            },
        ):
            from logger_service.service.chat_image.nats_publisher import _ensure_stream

            await _ensure_stream(config, js)

        js.add_stream.assert_awaited_once()
        stream_config = js.add_stream.await_args.kwargs["config"]
        self.assertEqual(stream_config.name, "CHAT_IMAGE_TAGGER_TASKS")
        self.assertEqual(stream_config.subjects, ["chat.image.tagger.task"])
        js.update_stream.assert_not_awaited()

    async def test_ensure_stream_updates_missing_subjects(self) -> None:
        config = self._build_config(jetstream_enabled=True)
        stream_config = SimpleNamespace(subjects=["old.subject"])
        stream_info = SimpleNamespace(config=stream_config)

        class RetentionPolicy:
            LIMITS = "limits"

        class StorageType:
            FILE = "file"

        class StreamConfig:
            def __init__(self, **kwargs: object) -> None:
                self.__dict__.update(kwargs)

        api_module = types.ModuleType("nats.js.api")
        api_module.RetentionPolicy = RetentionPolicy
        api_module.StorageType = StorageType
        api_module.StreamConfig = StreamConfig
        js = SimpleNamespace(
            stream_info=AsyncMock(return_value=stream_info),
            add_stream=AsyncMock(),
            update_stream=AsyncMock(),
        )
        with patch.dict(
            sys.modules,
            {
                "nats": types.ModuleType("nats"),
                "nats.js": types.ModuleType("nats.js"),
                "nats.js.api": api_module,
            },
        ):
            from logger_service.service.chat_image.nats_publisher import _ensure_stream

            await _ensure_stream(config, js)

        js.add_stream.assert_not_awaited()
        js.update_stream.assert_awaited_once_with(config=stream_config)
        self.assertEqual(
            stream_config.subjects, ["old.subject", "chat.image.tagger.task"]
        )

    async def test_get_or_connect_nats_resets_cached_jetstream_on_reconnect(
        self,
    ) -> None:
        config = self._build_config(jetstream_enabled=True)
        client = SimpleNamespace(is_connected=True)
        nats_module = types.ModuleType("nats")
        nats_module.connect = AsyncMock(return_value=client)

        from logger_service.service.chat_image import nats_publisher

        nats_publisher._nats_client = SimpleNamespace(is_connected=False)
        nats_publisher._jetstream_context = object()
        nats_publisher._ensured_streams = {
            ("CHAT_IMAGE_TAGGER_TASKS", ("chat.image.tagger.task",))
        }

        with patch.dict(
            sys.modules,
            {
                "nats": nats_module,
            },
        ):
            connected = await nats_publisher._get_or_connect_nats(config)

        self.assertIs(connected, client)
        self.assertIsNone(nats_publisher._jetstream_context)
        self.assertEqual(nats_publisher._ensured_streams, set())


if __name__ == "__main__":
    unittest.main()
