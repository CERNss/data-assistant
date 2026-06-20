from __future__ import annotations

import asyncio
import sys
import types
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from contracts.chat_image_task import TaskV2
from processor_service.service.chat_image.config import (
    ChatImageConfig,
    NatsTaskBusConfig,
    TaggerPipelineConfig,
)
from processor_service.service.chat_image.tagger_worker import handle_nats_message


class TestChatImageTaggerWorker(unittest.IsolatedAsyncioTestCase):
    def _build_config(self, *, auto_run: bool = False) -> ChatImageConfig:
        return ChatImageConfig(
            save_root=Path("data/chat_images"),
            nats=NatsTaskBusConfig(
                enabled=True,
                servers=("nats://127.0.0.1:4222",),
                subject="chat.image.tagger.task",
                queue_group="chat-image-tagger-workers",
                client_name="data-assistant",
                connect_timeout_sec=5.0,
                jetstream_enabled=True,
                stream_name="CHAT_IMAGE_TAGGER_TASKS",
                stream_subjects=("chat.image.tagger.task",),
                durable_name="chat-image-tagger-workers",
                ack_wait_sec=120.0,
                max_deliver=10,
            ),
            tagger=TaggerPipelineConfig(
                enabled=True,
                auto_run=auto_run,
                drain_interval_sec=10.0,
                healthcheck_path="/healthz",
                base_url="http://tagger:8000",
                threshold=0.5,
                use_chinese_name=True,
                top_k=20,
                queue_file=Path("data/chat_image_tagger_queue.json"),
                audit_log_file=Path("data/group_image_tags.jsonl"),
                batch_size=16,
                timeout_sec=3600.0,
                max_attempts=3,
            ),
        )

    async def test_handle_message_ignores_invalid_payload(self) -> None:
        config = self._build_config()
        with (
            patch(
                "processor_service.service.chat_image.tagger_worker.decode_task",
                side_effect=ValueError("bad payload"),
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker.enqueue_tagger_task_payload",
                new=AsyncMock(),
            ) as enqueue_mock,
        ):
            await handle_nats_message(config=config, data=b"{}", subject="test.subject")

        enqueue_mock.assert_not_awaited()

    async def test_handle_message_enqueues_without_sync_tagger_run(self) -> None:
        config = self._build_config(auto_run=False)
        task = TaskV2(
            version=2,
            image_id=1,
            sha256="abc123",
            source_url="https://example.com/a.png",
            original_url="https://example.com/a.png",
            context={"message_id": "1", "seq": 0},
            image_path="/tmp/a.png",
        )
        with (
            patch(
                "processor_service.service.chat_image.tagger_worker.decode_task",
                return_value=task,
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker._resolve_task_image_path",
                return_value="/tmp/a.png",
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker.enqueue_tagger_task_payload",
                new=AsyncMock(),
            ) as enqueue_mock,
            patch(
                "processor_service.service.chat_image.tagger_worker.run_tagger_once",
                new=AsyncMock(),
            ) as run_once_mock,
            patch(
                "processor_service.service.chat_image.tagger_worker.ensure_tagger_auto_run",
                new=AsyncMock(),
            ) as auto_run_mock,
        ):
            await handle_nats_message(config=config, data=b"{}", subject="test.subject")

        enqueue_mock.assert_awaited_once()
        run_once_mock.assert_not_awaited()
        auto_run_mock.assert_not_awaited()

    async def test_handle_message_swallows_processing_error(self) -> None:
        config = self._build_config(auto_run=False)
        task = TaskV2(
            version=2,
            image_id=1,
            sha256="abc123",
            source_url="https://example.com/a.png",
            original_url="https://example.com/a.png",
            context={"message_id": "1", "seq": 0},
            image_path="/tmp/a.png",
        )
        with (
            patch(
                "processor_service.service.chat_image.tagger_worker.decode_task",
                return_value=task,
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker._resolve_task_image_path",
                return_value="/tmp/a.png",
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker.enqueue_tagger_task_payload",
                new=AsyncMock(side_effect=RuntimeError("disk error")),
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker.run_tagger_once",
                new=AsyncMock(),
            ) as run_once_mock,
        ):
            await handle_nats_message(config=config, data=b"{}", subject="test.subject")

        run_once_mock.assert_not_awaited()

    async def test_ack_or_nak_message_acks_success(self) -> None:
        msg = SimpleNamespace(
            data=b"{}",
            subject="test.subject",
            metadata=object(),
            ack=AsyncMock(),
            nak=AsyncMock(),
        )
        from processor_service.service.chat_image.tagger_worker import (
            _ack_or_nak_message,
        )

        await _ack_or_nak_message(msg, success=True)

        msg.ack.assert_awaited_once()
        msg.nak.assert_not_awaited()

    async def test_ack_or_nak_message_naks_failure(self) -> None:
        msg = SimpleNamespace(
            data=b"{}",
            subject="test.subject",
            metadata=object(),
            ack=AsyncMock(),
            nak=AsyncMock(),
        )
        from processor_service.service.chat_image.tagger_worker import (
            _ack_or_nak_message,
        )

        await _ack_or_nak_message(msg, success=False)

        msg.ack.assert_not_awaited()
        msg.nak.assert_awaited_once()

    async def test_ack_or_nak_message_skips_core_message(self) -> None:
        msg = SimpleNamespace(
            data=b"{}",
            subject="test.subject",
            metadata=None,
            ack=AsyncMock(),
            nak=AsyncMock(),
        )
        from processor_service.service.chat_image.tagger_worker import (
            _ack_or_nak_message,
        )

        await _ack_or_nak_message(msg, success=True)

        msg.ack.assert_not_awaited()
        msg.nak.assert_not_awaited()

    async def test_process_message_returns_false_for_unresolved_path(self) -> None:
        config = self._build_config(auto_run=False)
        task = TaskV2(
            version=2,
            image_id=1,
            sha256="abc123",
            source_url="https://example.com/a.png",
            original_url="https://example.com/a.png",
            context={"message_id": "1", "seq": 0},
        )
        with (
            patch(
                "processor_service.service.chat_image.tagger_worker.decode_task",
                return_value=task,
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker._resolve_task_image_path",
                return_value=None,
            ),
        ):
            from processor_service.service.chat_image.tagger_worker import (
                _process_tagger_task_message,
            )

            success = await _process_tagger_task_message(
                config=config, data=b"{}", subject="test.subject"
            )

        self.assertFalse(success)

    def test_build_consumer_config_uses_durable_manual_ack_settings(self) -> None:
        config = self._build_config(auto_run=False)

        class AckPolicy:
            EXPLICIT = "explicit"

        class DeliverPolicy:
            ALL = "all"

        class ConsumerConfig:
            def __init__(self, **kwargs: object) -> None:
                self.__dict__.update(kwargs)

        api_module = types.ModuleType("nats.js.api")
        api_module.AckPolicy = AckPolicy
        api_module.ConsumerConfig = ConsumerConfig
        api_module.DeliverPolicy = DeliverPolicy
        with patch.dict(
            sys.modules,
            {
                "nats": types.ModuleType("nats"),
                "nats.js": types.ModuleType("nats.js"),
                "nats.js.api": api_module,
            },
        ):
            from processor_service.service.chat_image.tagger_worker import (
                _build_consumer_config,
            )

            consumer_config = _build_consumer_config(config)

        self.assertEqual(consumer_config.durable_name, "chat-image-tagger-workers")
        self.assertEqual(consumer_config.deliver_policy, "all")
        self.assertEqual(consumer_config.ack_policy, "explicit")
        self.assertEqual(consumer_config.ack_wait, 120.0)
        self.assertEqual(consumer_config.max_deliver, 10)
        self.assertEqual(consumer_config.filter_subject, "chat.image.tagger.task")
        self.assertEqual(consumer_config.deliver_group, "chat-image-tagger-workers")

    def test_validate_jetstream_queue_config_rejects_durable_mismatch(self) -> None:
        config = self._build_config(auto_run=False)
        config = ChatImageConfig(
            save_root=config.save_root,
            nats=replace(config.nats, durable_name="chat-image-tagger-worker"),
            tagger=config.tagger,
        )

        from processor_service.service.chat_image.tagger_worker import (
            _validate_jetstream_queue_config,
        )

        with self.assertRaisesRegex(
            ValueError,
            "CHAT_IMAGE_NATS_DURABLE must equal CHAT_IMAGE_NATS_QUEUE_GROUP",
        ):
            _validate_jetstream_queue_config(config)

    def test_validate_jetstream_queue_config_allows_core_nats_mismatch(self) -> None:
        config = self._build_config(auto_run=False)
        config = ChatImageConfig(
            save_root=config.save_root,
            nats=replace(
                config.nats,
                jetstream_enabled=False,
                durable_name="chat-image-tagger-worker",
            ),
            tagger=config.tagger,
        )

        from processor_service.service.chat_image.tagger_worker import (
            _validate_jetstream_queue_config,
        )

        _validate_jetstream_queue_config(config)

    async def test_ensure_jetstream_stream_adds_missing_stream(self) -> None:
        config = self._build_config(auto_run=False)

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
            from processor_service.service.chat_image.tagger_worker import (
                _ensure_jetstream_stream,
            )

            await _ensure_jetstream_stream(config, js)

        js.stream_info.assert_awaited_once_with("CHAT_IMAGE_TAGGER_TASKS")
        js.add_stream.assert_awaited_once()
        stream_config = js.add_stream.await_args.kwargs["config"]
        self.assertEqual(stream_config.name, "CHAT_IMAGE_TAGGER_TASKS")
        self.assertEqual(stream_config.subjects, ["chat.image.tagger.task"])
        self.assertEqual(stream_config.max_age, 604800.0)
        self.assertEqual(stream_config.max_bytes, -1)
        self.assertEqual(stream_config.max_msgs, -1)
        js.update_stream.assert_not_awaited()

    async def test_ensure_jetstream_stream_updates_missing_subjects(self) -> None:
        config = self._build_config(auto_run=False)
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
            from processor_service.service.chat_image.tagger_worker import (
                _ensure_jetstream_stream,
            )

            await _ensure_jetstream_stream(config, js)

        js.add_stream.assert_not_awaited()
        js.update_stream.assert_awaited_once_with(config=stream_config)
        self.assertEqual(stream_config.subjects, ["old.subject", "chat.image.tagger.task"])

    async def test_periodic_queue_drain_skips_when_tagger_unhealthy(self) -> None:
        config = self._build_config(auto_run=False)
        config = ChatImageConfig(
            save_root=config.save_root,
            nats=config.nats,
            tagger=replace(config.tagger, drain_interval_sec=0.5),
        )
        stop_event = asyncio.Event()
        from processor_service.service.chat_image.tagger_worker import (
            _periodic_queue_drain,
        )

        async def stop_after_skip(*_: object, **__: object) -> bool:
            stop_event.set()
            return False

        with (
            patch(
                "processor_service.service.chat_image.tagger_worker._is_tagger_healthy",
                new=AsyncMock(side_effect=stop_after_skip),
            ) as healthy_mock,
            patch(
                "processor_service.service.chat_image.tagger_worker.run_tagger_once",
                new=AsyncMock(),
            ) as run_once_mock,
        ):
            await _periodic_queue_drain(config=config, stop_event=stop_event)

        healthy_mock.assert_awaited_once_with(config)
        run_once_mock.assert_not_awaited()

    async def test_periodic_queue_drain_runs_when_tagger_healthy(self) -> None:
        config = self._build_config(auto_run=False)
        config = ChatImageConfig(
            save_root=config.save_root,
            nats=config.nats,
            tagger=replace(config.tagger, drain_interval_sec=0.5),
        )
        stop_event = asyncio.Event()
        from processor_service.service.chat_image.tagger_worker import (
            _periodic_queue_drain,
        )

        async def run_once_and_stop(*_: object, **__: object) -> dict[str, int]:
            stop_event.set()
            return {"picked": 1, "success": 1, "failed": 0, "requeued": 0}

        with (
            patch(
                "processor_service.service.chat_image.tagger_worker._is_tagger_healthy",
                new=AsyncMock(return_value=True),
            ) as healthy_mock,
            patch(
                "processor_service.service.chat_image.tagger_worker.run_tagger_once",
                new=AsyncMock(side_effect=run_once_and_stop),
            ) as run_once_mock,
        ):
            await _periodic_queue_drain(config=config, stop_event=stop_event)

        healthy_mock.assert_awaited_once_with(config)
        run_once_mock.assert_awaited_once_with(config)

    async def test_run_skips_startup_backlog_when_tagger_unhealthy(self) -> None:
        config = self._build_config(auto_run=False)

        class FakeNatsConnection:
            is_closed = False

            def jetstream(self) -> SimpleNamespace:
                return SimpleNamespace(subscribe=AsyncMock())

            async def drain(self) -> None:
                return None

        fake_nc = FakeNatsConnection()
        nats_module = types.ModuleType("nats")
        nats_module.connect = AsyncMock(return_value=fake_nc)
        stop_event = asyncio.Event()

        async def stop_after_subscribe(*_: object, **__: object) -> None:
            stop_event.set()

        with (
            patch(
                "processor_service.service.chat_image.tagger_worker.load_chat_image_config",
                return_value=config,
            ),
            patch.dict(sys.modules, {"nats": nats_module}),
            patch(
                "processor_service.service.chat_image.tagger_worker._ensure_jetstream_stream",
                new=AsyncMock(),
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker._build_consumer_config",
                return_value=object(),
            ),
            patch(
                "processor_service.service.chat_image.tagger_worker._is_tagger_healthy",
                new=AsyncMock(return_value=False),
            ) as healthy_mock,
            patch(
                "processor_service.service.chat_image.tagger_worker.run_tagger_until_empty",
                new=AsyncMock(),
            ) as run_until_empty_mock,
            patch(
                "processor_service.service.chat_image.tagger_worker._periodic_queue_drain",
                new=AsyncMock(side_effect=stop_after_subscribe),
            ),
        ):
            from processor_service.service.chat_image.tagger_worker import _run

            result = await _run(process_backlog=True, stop_event=stop_event)

        self.assertEqual(result, 0)
        healthy_mock.assert_awaited_once_with(config)
        run_until_empty_mock.assert_not_awaited()


class TestNatsLifecycleCallbacks(unittest.IsolatedAsyncioTestCase):
    async def test_closed_callback_requests_restart(self) -> None:
        from processor_service.service.chat_image.tagger_worker import (
            _make_nats_lifecycle_callbacks,
        )

        shutdown_event = asyncio.Event()
        nats_closed = asyncio.Event()
        _, _, _, on_closed = _make_nats_lifecycle_callbacks(
            shutdown_event, nats_closed
        )

        await on_closed()

        self.assertTrue(nats_closed.is_set())
        self.assertTrue(shutdown_event.is_set())

    async def test_closed_callback_noop_during_graceful_shutdown(self) -> None:
        from processor_service.service.chat_image.tagger_worker import (
            _make_nats_lifecycle_callbacks,
        )

        shutdown_event = asyncio.Event()
        shutdown_event.set()
        nats_closed = asyncio.Event()
        _, _, _, on_closed = _make_nats_lifecycle_callbacks(
            shutdown_event, nats_closed
        )

        await on_closed()

        # An expected close during shutdown must not flag a restart.
        self.assertFalse(nats_closed.is_set())


class TestAckOrNakBackoff(unittest.IsolatedAsyncioTestCase):
    def _msg(self) -> SimpleNamespace:
        return SimpleNamespace(
            subject="s", metadata=object(), ack=AsyncMock(), nak=AsyncMock()
        )

    async def test_nak_uses_delay_when_configured(self) -> None:
        from processor_service.service.chat_image.tagger_worker import (
            _ack_or_nak_message,
        )

        msg = self._msg()
        await _ack_or_nak_message(msg, success=False, nak_delay_sec=5.0)
        msg.nak.assert_awaited_once_with(delay=5.0)

    async def test_nak_without_delay_when_zero(self) -> None:
        from processor_service.service.chat_image.tagger_worker import (
            _ack_or_nak_message,
        )

        msg = self._msg()
        await _ack_or_nak_message(msg, success=False, nak_delay_sec=0.0)
        msg.nak.assert_awaited_once_with()


class TestWorkerLiveness(unittest.TestCase):
    def tearDown(self) -> None:
        from processor_service.service.chat_image import tagger_worker

        tagger_worker.reset_nats_liveness(required=False)

    def test_healthy_when_nats_not_required(self) -> None:
        from processor_service.service.chat_image import tagger_worker

        tagger_worker.reset_nats_liveness(required=False)
        self.assertTrue(tagger_worker.worker_is_healthy())

    def test_unhealthy_when_required_and_disconnected(self) -> None:
        from processor_service.service.chat_image import tagger_worker

        tagger_worker.reset_nats_liveness(required=True)
        self.assertFalse(tagger_worker.worker_is_healthy())

    def test_healthy_when_required_and_connected(self) -> None:
        from processor_service.service.chat_image import tagger_worker

        tagger_worker.reset_nats_liveness(required=True)
        tagger_worker.set_nats_connected(True)
        self.assertTrue(tagger_worker.worker_is_healthy())


if __name__ == "__main__":
    unittest.main()
