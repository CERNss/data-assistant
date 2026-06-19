import json
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

from processor_service.service.chat_image.config import (
    ChatImageConfig,
    NatsTaskBusConfig,
    TaggerPipelineConfig,
)
from processor_service.service.chat_image.tagger_pipeline import (
    enqueue_image_for_tagging,
    get_pending_tagger_count,
    run_tagger_once,
)


class TestChatImageTaggerPipeline(unittest.IsolatedAsyncioTestCase):
    _tmpdir: tempfile.TemporaryDirectory[str] | None = None
    _config: ChatImageConfig | None = None

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self._config = ChatImageConfig(
            save_root=root / "images",
            nats=NatsTaskBusConfig(
                enabled=False,
                servers=("nats://127.0.0.1:4222",),
                subject="chat.image.tagger.task",
                queue_group="chat-image-tagger-workers",
                client_name="test",
                connect_timeout_sec=3.0,
            ),
            tagger=TaggerPipelineConfig(
                enabled=True,
                auto_run=False,
                base_url="http://tagger:8000",
                threshold=0.5,
                use_chinese_name=True,
                top_k=20,
                queue_file=root / "queue.json",
                audit_log_file=root / "tagger_audit.jsonl",
                batch_size=4,
                timeout_sec=30.0,
                max_attempts=2,
            ),
        )

    def tearDown(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()

    async def test_enqueue_is_deduplicated(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        image_path = Path(self._tmpdir.name) / "image.png"
        image_path.write_bytes(b"abc")

        await enqueue_image_for_tagging(
            config=config, image_path=image_path, context={}
        )
        await enqueue_image_for_tagging(
            config=config, image_path=image_path, context={}
        )

        self.assertEqual(get_pending_tagger_count(config), 1)

    async def test_run_once_success(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        image_path = Path(self._tmpdir.name) / "image-success.png"
        image_path.write_bytes(b"abc")
        await enqueue_image_for_tagging(
            config=config, image_path=image_path, context={"m": "1"}
        )

        async def fake_runner(
            _: ChatImageConfig,
            items: list[dict[str, object]],
        ) -> list[dict[str, object]]:
            return [
                {"item": item, "status": "success", "tags": ["cat", "outdoor"]}
                for item in items
            ]

        summary = await run_tagger_once(config, runner=fake_runner)
        self.assertEqual(summary["picked"], 1)
        self.assertEqual(summary["success"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["requeued"], 0)
        self.assertEqual(get_pending_tagger_count(config), 0)

        lines = (
            config.tagger.audit_log_file.read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["tag_count"], 2)

    async def test_run_once_uses_http_batch_response(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        image_path = Path(self._tmpdir.name) / "image-http.png"
        image_path.write_bytes(b"abc")
        await enqueue_image_for_tagging(
            config=config, image_path=image_path, context={"m": "http"}
        )

        expected_path = str(image_path.resolve())
        with patch(
            "processor_service.service.chat_image.tagger_pipeline._post_tagger_batch",
            new=AsyncMock(
                return_value={
                    "provider": "CUDAExecutionProvider",
                    "results": [
                        {
                            "image_path": expected_path,
                            "success": True,
                            "tags": [
                                {"name": "cat", "score": 0.9},
                                {"name": "outdoor", "score": 0.8},
                            ],
                            "elapsed_ms": 12,
                        }
                    ],
                }
            ),
        ) as post_mock:
            summary = await run_tagger_once(config)

        self.assertEqual(summary["picked"], 1)
        self.assertEqual(summary["success"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["requeued"], 0)
        post_mock.assert_awaited_once_with(
            base_url="http://tagger:8000",
            payload={
                "image_paths": [expected_path],
                "threshold": 0.5,
                "use_chinese_name": True,
                "top_k": 20,
            },
            timeout_sec=30.0,
        )

        payload = json.loads(
            config.tagger.audit_log_file.read_text(encoding="utf-8").strip()
        )
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["tags"], ["cat", "outdoor"])

    async def test_run_once_matches_http_results_by_image_path(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        first_path = Path(self._tmpdir.name) / "first.png"
        second_path = Path(self._tmpdir.name) / "second.png"
        first_path.write_bytes(b"first")
        second_path.write_bytes(b"second")
        await enqueue_image_for_tagging(
            config=config, image_path=first_path, context={"name": "first"}
        )
        await enqueue_image_for_tagging(
            config=config, image_path=second_path, context={"name": "second"}
        )

        first_resolved = str(first_path.resolve())
        second_resolved = str(second_path.resolve())
        with patch(
            "processor_service.service.chat_image.tagger_pipeline._post_tagger_batch",
            new=AsyncMock(
                return_value={
                    "results": [
                        {
                            "image_path": second_resolved,
                            "success": True,
                            "tags": [{"name": "second-tag"}],
                        },
                        {
                            "image_path": first_resolved,
                            "success": True,
                            "tags": [{"name": "first-tag"}],
                        },
                    ],
                }
            ),
        ):
            summary = await run_tagger_once(config)

        self.assertEqual(summary["success"], 2)
        lines = (
            config.tagger.audit_log_file.read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        payloads = [json.loads(line) for line in lines]
        tags_by_path = {
            payload["image_path"]: payload["tags"]
            for payload in payloads
            if payload["status"] == "success"
        }
        self.assertEqual(tags_by_path[first_resolved], ["first-tag"])
        self.assertEqual(tags_by_path[second_resolved], ["second-tag"])

    async def test_corrupt_queue_file_is_archived_before_enqueue(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        image_path = Path(self._tmpdir.name) / "image-after-corrupt.png"
        image_path.write_bytes(b"abc")
        config.tagger.queue_file.write_text("{not-json", encoding="utf-8")

        await enqueue_image_for_tagging(
            config=config, image_path=image_path, context={}
        )

        archives = list(config.tagger.queue_file.parent.glob("queue.json.corrupt.*"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_text(encoding="utf-8"), "{not-json")
        queue_payload = json.loads(
            config.tagger.queue_file.read_text(encoding="utf-8")
        )
        self.assertEqual(len(queue_payload), 1)
        self.assertEqual(queue_payload[0]["image_path"], str(image_path.resolve()))

    async def test_inflight_queue_items_are_restored(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        image_path = Path(self._tmpdir.name) / "image-inflight.png"
        image_path.write_bytes(b"abc")
        resolved_path = str(image_path.resolve())
        inflight_file = config.tagger.queue_file.with_suffix(
            config.tagger.queue_file.suffix + ".inflight"
        )
        inflight_file.write_text(
            json.dumps(
                [
                    {
                        "image_path": resolved_path,
                        "context": {"m": "inflight"},
                        "enqueued_at": "2026-01-01T00:00:00+00:00",
                        "attempt_count": 0,
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.assertEqual(get_pending_tagger_count(config), 1)
        self.assertFalse(inflight_file.exists())

        async def fake_runner(
            _: ChatImageConfig,
            items: list[dict[str, object]],
        ) -> list[dict[str, object]]:
            return [
                {"item": item, "status": "success", "tags": ["restored"]}
                for item in items
            ]

        summary = await run_tagger_once(config, runner=fake_runner)

        self.assertEqual(summary["picked"], 1)
        self.assertEqual(summary["success"], 1)
        self.assertEqual(get_pending_tagger_count(config), 0)
        payload = json.loads(
            config.tagger.audit_log_file.read_text(encoding="utf-8").strip()
        )
        self.assertEqual(payload["tags"], ["restored"])

    async def test_run_once_requeue_then_fail(self) -> None:
        assert self._tmpdir is not None
        config = cast(ChatImageConfig, self._config)
        image_path = Path(self._tmpdir.name) / "image-fail.png"
        image_path.write_bytes(b"abc")
        await enqueue_image_for_tagging(
            config=config, image_path=image_path, context={}
        )

        async def fail_runner(
            _: ChatImageConfig,
            items: list[dict[str, object]],
        ) -> list[dict[str, object]]:
            return [
                {"item": item, "status": "failed", "error": "boom"} for item in items
            ]

        first = await run_tagger_once(config, runner=fail_runner)
        self.assertEqual(first["picked"], 1)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(first["requeued"], 1)
        self.assertEqual(get_pending_tagger_count(config), 1)

        second = await run_tagger_once(config, runner=fail_runner)
        self.assertEqual(second["picked"], 1)
        self.assertEqual(second["failed"], 1)
        self.assertEqual(second["requeued"], 0)
        self.assertEqual(get_pending_tagger_count(config), 0)

        lines = (
            config.tagger.audit_log_file.read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        statuses = [json.loads(line)["status"] for line in lines]
        self.assertEqual(statuses, ["retrying", "failed"])
