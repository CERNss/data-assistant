import os
import unittest
from pathlib import Path

from plugins.chat_image.config import load_chat_image_config


class TestChatImageConfig(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_defaults(self) -> None:
        os.environ.pop("CHAT_IMAGE_SAVE_DIR", None)
        os.environ.pop("GROUP_IMAGE_SAVE_DIR", None)
        os.environ.pop("GROUP_IMAGE_TIMEOUT_SEC", None)
        os.environ.pop("GROUP_IMAGE_RETRY_COUNT", None)
        os.environ.pop("GROUP_IMAGE_RETRY_DELAY_SEC", None)
        os.environ.pop("CHAT_IMAGE_NATS_ENABLED", None)
        os.environ.pop("CHAT_IMAGE_NATS_SERVERS", None)
        os.environ.pop("CHAT_IMAGE_NATS_SUBJECT", None)
        os.environ.pop("CHAT_IMAGE_NATS_QUEUE_GROUP", None)
        os.environ.pop("CHAT_IMAGE_NATS_CLIENT_NAME", None)
        os.environ.pop("CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC", None)
        os.environ.pop("CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC", None)
        os.environ.pop("CHAT_IMAGE_NATS_FALLBACK_LOCAL_QUEUE", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_ENABLED", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_AUTO_RUN", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_PYTHON", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_TOOL_ROOT", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_ENTRY_SCRIPT", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_CONFIG", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_QUEUE_FILE", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_RUN_ROOT", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_AUDIT_LOG_FILE", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_BATCH_SIZE", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_TIMEOUT_SEC", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_MAX_ATTEMPTS", None)
        os.environ.pop("CHAT_IMAGE_TAGGER_KEEP_RUN_ARTIFACTS", None)

        cfg = load_chat_image_config()
        self.assertEqual(cfg.save_root, Path("data/chat_images"))
        self.assertEqual(cfg.timeout_sec, 20.0)
        self.assertEqual(cfg.retry_count, 3)
        self.assertEqual(cfg.retry_delay_sec, 0.8)
        self.assertEqual(cfg.audit_log_file, Path("data/group_images.jsonl"))
        self.assertFalse(cfg.nats.enabled)
        self.assertEqual(cfg.nats.servers, ("nats://127.0.0.1:4222",))
        self.assertEqual(cfg.nats.subject, "chat.image.tagger.task")
        self.assertEqual(cfg.nats.queue_group, "chat-image-tagger-workers")
        self.assertEqual(cfg.nats.client_name, "data-logger")
        self.assertEqual(cfg.nats.connect_timeout_sec, 5.0)
        self.assertEqual(cfg.nats.publish_timeout_sec, 3.0)
        self.assertTrue(cfg.nats.fallback_to_local_queue)
        self.assertFalse(cfg.tagger.enabled)
        self.assertFalse(cfg.tagger.auto_run)
        self.assertEqual(cfg.tagger.python_bin, "python")
        self.assertIsNone(cfg.tagger.tool_root)
        self.assertEqual(cfg.tagger.entry_script, Path("main.py"))
        self.assertEqual(cfg.tagger.config_file, Path("config.ini"))
        self.assertEqual(cfg.tagger.queue_file, Path("data/chat_image_tagger_queue.json"))
        self.assertEqual(cfg.tagger.run_root, Path("data/chat_image_tagger_runs"))
        self.assertEqual(cfg.tagger.audit_log_file, Path("data/group_image_tags.jsonl"))
        self.assertEqual(cfg.tagger.batch_size, 16)
        self.assertEqual(cfg.tagger.timeout_sec, 3600.0)
        self.assertEqual(cfg.tagger.max_attempts, 3)
        self.assertFalse(cfg.tagger.keep_run_artifacts)

    def test_overrides(self) -> None:
        os.environ["CHAT_IMAGE_SAVE_DIR"] = "/tmp/chat-images"
        os.environ["GROUP_IMAGE_TIMEOUT_SEC"] = "5"
        os.environ["GROUP_IMAGE_RETRY_COUNT"] = "2"
        os.environ["GROUP_IMAGE_RETRY_DELAY_SEC"] = "0.2"
        os.environ["CHAT_IMAGE_NATS_ENABLED"] = "true"
        os.environ["CHAT_IMAGE_NATS_SERVERS"] = "nats://127.0.0.1:4222,nats://127.0.0.1:4223"
        os.environ["CHAT_IMAGE_NATS_SUBJECT"] = "task.subject"
        os.environ["CHAT_IMAGE_NATS_QUEUE_GROUP"] = "workers-a"
        os.environ["CHAT_IMAGE_NATS_CLIENT_NAME"] = "collector"
        os.environ["CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC"] = "9"
        os.environ["CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC"] = "7"
        os.environ["CHAT_IMAGE_NATS_FALLBACK_LOCAL_QUEUE"] = "false"
        os.environ["CHAT_IMAGE_TAGGER_ENABLED"] = "true"
        os.environ["CHAT_IMAGE_TAGGER_AUTO_RUN"] = "1"
        os.environ["CHAT_IMAGE_TAGGER_PYTHON"] = "python3"
        os.environ["CHAT_IMAGE_TAGGER_TOOL_ROOT"] = "/tmp/eagle-tagger"
        os.environ["CHAT_IMAGE_TAGGER_ENTRY_SCRIPT"] = "entry.py"
        os.environ["CHAT_IMAGE_TAGGER_CONFIG"] = "tagger.ini"
        os.environ["CHAT_IMAGE_TAGGER_QUEUE_FILE"] = "/tmp/tagger-queue.json"
        os.environ["CHAT_IMAGE_TAGGER_RUN_ROOT"] = "/tmp/tagger-runs"
        os.environ["CHAT_IMAGE_TAGGER_AUDIT_LOG_FILE"] = "/tmp/tagger-audit.jsonl"
        os.environ["CHAT_IMAGE_TAGGER_BATCH_SIZE"] = "12"
        os.environ["CHAT_IMAGE_TAGGER_TIMEOUT_SEC"] = "88"
        os.environ["CHAT_IMAGE_TAGGER_MAX_ATTEMPTS"] = "5"
        os.environ["CHAT_IMAGE_TAGGER_KEEP_RUN_ARTIFACTS"] = "yes"

        cfg = load_chat_image_config()
        self.assertEqual(cfg.save_root, Path("/tmp/chat-images"))
        self.assertEqual(cfg.timeout_sec, 5.0)
        self.assertEqual(cfg.retry_count, 2)
        self.assertEqual(cfg.retry_delay_sec, 0.2)
        self.assertTrue(cfg.nats.enabled)
        self.assertEqual(
            cfg.nats.servers,
            ("nats://127.0.0.1:4222", "nats://127.0.0.1:4223"),
        )
        self.assertEqual(cfg.nats.subject, "task.subject")
        self.assertEqual(cfg.nats.queue_group, "workers-a")
        self.assertEqual(cfg.nats.client_name, "collector")
        self.assertEqual(cfg.nats.connect_timeout_sec, 9.0)
        self.assertEqual(cfg.nats.publish_timeout_sec, 7.0)
        self.assertFalse(cfg.nats.fallback_to_local_queue)
        self.assertTrue(cfg.tagger.enabled)
        self.assertTrue(cfg.tagger.auto_run)
        self.assertEqual(cfg.tagger.python_bin, "python3")
        self.assertEqual(cfg.tagger.tool_root, Path("/tmp/eagle-tagger"))
        self.assertEqual(cfg.tagger.entry_script, Path("entry.py"))
        self.assertEqual(cfg.tagger.config_file, Path("tagger.ini"))
        self.assertEqual(cfg.tagger.queue_file, Path("/tmp/tagger-queue.json"))
        self.assertEqual(cfg.tagger.run_root, Path("/tmp/tagger-runs"))
        self.assertEqual(cfg.tagger.audit_log_file, Path("/tmp/tagger-audit.jsonl"))
        self.assertEqual(cfg.tagger.batch_size, 12)
        self.assertEqual(cfg.tagger.timeout_sec, 88.0)
        self.assertEqual(cfg.tagger.max_attempts, 5)
        self.assertTrue(cfg.tagger.keep_run_artifacts)
