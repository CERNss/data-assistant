import json
import tempfile
import unittest
from pathlib import Path

from plugins.chat_image.config import ChatImageConfig, TaggerPipelineConfig
from plugins.chat_image.tagger_pipeline import (
    enqueue_image_for_tagging,
    get_pending_tagger_count,
    run_tagger_once,
)


class TestChatImageTaggerPipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self._config = ChatImageConfig(
            save_root=root / "images",
            timeout_sec=20.0,
            retry_count=3,
            retry_delay_sec=0.8,
            audit_log_file=root / "group_images.jsonl",
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
        self._config.tagger.tool_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    async def test_enqueue_is_deduplicated(self) -> None:
        image_path = Path(self._tmpdir.name) / "image.png"
        image_path.write_bytes(b"abc")

        await enqueue_image_for_tagging(config=self._config, image_path=image_path, context={})
        await enqueue_image_for_tagging(config=self._config, image_path=image_path, context={})

        self.assertEqual(get_pending_tagger_count(self._config), 1)

    async def test_run_once_success(self) -> None:
        image_path = Path(self._tmpdir.name) / "image-success.png"
        image_path.write_bytes(b"abc")
        await enqueue_image_for_tagging(config=self._config, image_path=image_path, context={"m": "1"})

        async def fake_runner(_: ChatImageConfig, items: list[dict]) -> list[dict]:
            return [{"item": item, "status": "success", "tags": ["cat", "outdoor"]} for item in items]

        summary = await run_tagger_once(self._config, runner=fake_runner)
        self.assertEqual(summary["picked"], 1)
        self.assertEqual(summary["success"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["requeued"], 0)
        self.assertEqual(get_pending_tagger_count(self._config), 0)

        lines = self._config.tagger.audit_log_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["tag_count"], 2)

    async def test_run_once_requeue_then_fail(self) -> None:
        image_path = Path(self._tmpdir.name) / "image-fail.png"
        image_path.write_bytes(b"abc")
        await enqueue_image_for_tagging(config=self._config, image_path=image_path, context={})

        async def fail_runner(_: ChatImageConfig, items: list[dict]) -> list[dict]:
            return [{"item": item, "status": "failed", "error": "boom"} for item in items]

        first = await run_tagger_once(self._config, runner=fail_runner)
        self.assertEqual(first["picked"], 1)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(first["requeued"], 1)
        self.assertEqual(get_pending_tagger_count(self._config), 1)

        second = await run_tagger_once(self._config, runner=fail_runner)
        self.assertEqual(second["picked"], 1)
        self.assertEqual(second["failed"], 1)
        self.assertEqual(second["requeued"], 0)
        self.assertEqual(get_pending_tagger_count(self._config), 0)

        lines = self._config.tagger.audit_log_file.read_text(encoding="utf-8").strip().splitlines()
        statuses = [json.loads(line)["status"] for line in lines]
        self.assertEqual(statuses, ["retrying", "failed"])
