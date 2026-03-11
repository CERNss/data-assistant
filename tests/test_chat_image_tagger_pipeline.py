import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

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
                python_bin="python",
                tool_root=root / "tool",
                entry_script=Path("main.py"),
                config_file=Path("config.ini"),
                queue_file=root / "queue.json",
                run_root=root / "runs",
                audit_log_file=root / "tagger_audit.jsonl",
                batch_size=4,
                timeout_sec=30.0,
                max_attempts=2,
                keep_run_artifacts=False,
            ),
        )
        config = cast(ChatImageConfig, self._config)
        tool_root = config.tagger.tool_root
        assert tool_root is not None
        tool_root.mkdir(parents=True, exist_ok=True)

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
