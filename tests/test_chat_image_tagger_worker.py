from __future__ import annotations

import unittest
from pathlib import Path
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
            ),
            tagger=TaggerPipelineConfig(
                enabled=True,
                auto_run=auto_run,
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

    async def test_handle_message_runs_once_when_auto_run_disabled(self) -> None:
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
        run_once_mock.assert_awaited_once_with(config)
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


if __name__ == "__main__":
    unittest.main()
