import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from plugins.chat_image.config import ChatImageConfig, NatsTaskBusConfig, TaggerPipelineConfig
from plugins.chat_image.tagger_worker import handle_nats_message


class TestChatImageTaggerWorker(unittest.IsolatedAsyncioTestCase):
    def _build_config(self, *, auto_run: bool = False) -> ChatImageConfig:
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
                queue_group="chat-image-tagger-workers",
                client_name="data-assistant",
                connect_timeout_sec=5.0,
                publish_timeout_sec=3.0,
                fallback_to_local_queue=True,
            ),
            tagger=TaggerPipelineConfig(
                enabled=True,
                auto_run=auto_run,
                python_bin="python",
                tool_root=Path("/tmp/tool"),
                entry_script=Path("main.py"),
                config_file=Path("config.ini"),
                queue_file=Path("data/chat_image_tagger_queue.json"),
                run_root=Path("data/chat_image_tagger_runs"),
                audit_log_file=Path("data/group_image_tags.jsonl"),
                batch_size=16,
                timeout_sec=3600.0,
                max_attempts=3,
                keep_run_artifacts=False,
            ),
        )

    async def test_handle_message_ignores_invalid_payload(self) -> None:
        config = self._build_config()
        with (
            patch(
                "plugins.chat_image.tagger_worker.decode_tagger_task_payload",
                side_effect=ValueError("bad payload"),
            ),
            patch(
                "plugins.chat_image.tagger_worker.enqueue_tagger_task_payload",
                new=AsyncMock(),
            ) as enqueue_mock,
        ):
            await handle_nats_message(config=config, data=b"{}", subject="test.subject")

        enqueue_mock.assert_not_awaited()

    async def test_handle_message_runs_once_when_auto_run_disabled(self) -> None:
        config = self._build_config(auto_run=False)
        with (
            patch(
                "plugins.chat_image.tagger_worker.decode_tagger_task_payload",
                return_value={"image_path": "/tmp/a.png", "context": {"m": "1"}},
            ),
            patch(
                "plugins.chat_image.tagger_worker.enqueue_tagger_task_payload",
                new=AsyncMock(),
            ) as enqueue_mock,
            patch("plugins.chat_image.tagger_worker.run_tagger_once", new=AsyncMock()) as run_once_mock,
            patch(
                "plugins.chat_image.tagger_worker.ensure_tagger_auto_run",
                new=AsyncMock(),
            ) as auto_run_mock,
        ):
            await handle_nats_message(config=config, data=b"{}", subject="test.subject")

        enqueue_mock.assert_awaited_once()
        run_once_mock.assert_awaited_once_with(config)
        auto_run_mock.assert_not_awaited()

    async def test_handle_message_swallows_processing_error(self) -> None:
        config = self._build_config(auto_run=False)
        with (
            patch(
                "plugins.chat_image.tagger_worker.decode_tagger_task_payload",
                return_value={"image_path": "/tmp/a.png", "context": {}},
            ),
            patch(
                "plugins.chat_image.tagger_worker.enqueue_tagger_task_payload",
                new=AsyncMock(side_effect=RuntimeError("disk error")),
            ),
            patch("plugins.chat_image.tagger_worker.run_tagger_once", new=AsyncMock()) as run_once_mock,
        ):
            await handle_nats_message(config=config, data=b"{}", subject="test.subject")

        run_once_mock.assert_not_awaited()
