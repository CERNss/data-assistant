from __future__ import annotations

import os
import unittest
from pathlib import Path

from logger_service.service.chat_image.config import (
    load_chat_image_config as load_logger_chat_image_config,
)
from processor_service.service.chat_image.config import (
    load_chat_image_config as load_processor_chat_image_config,
)


class TestLoggerChatImageConfig(unittest.TestCase):
    _env_backup: dict[str, str] = {}

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
        os.environ.pop("CHAT_IMAGE_NATS_CLIENT_NAME", None)
        os.environ.pop("CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC", None)
        os.environ.pop("CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC", None)

        cfg = load_logger_chat_image_config()
        self.assertEqual(cfg.save_root, Path("data/chat_images"))
        self.assertEqual(cfg.timeout_sec, 20.0)
        self.assertEqual(cfg.retry_count, 3)
        self.assertEqual(cfg.retry_delay_sec, 0.8)
        self.assertEqual(cfg.audit_log_file, Path("data/group_images.jsonl"))
        self.assertFalse(cfg.nats.enabled)
        self.assertEqual(cfg.nats.servers, ("nats://127.0.0.1:4222",))
        self.assertEqual(cfg.nats.subject, "chat.image.tagger.task")
        self.assertEqual(cfg.nats.client_name, "data-assistant")
        self.assertEqual(cfg.nats.connect_timeout_sec, 5.0)
        self.assertEqual(cfg.nats.publish_timeout_sec, 3.0)

    def test_overrides(self) -> None:
        os.environ["CHAT_IMAGE_SAVE_DIR"] = "/tmp/chat-images"
        os.environ["GROUP_IMAGE_TIMEOUT_SEC"] = "5"
        os.environ["GROUP_IMAGE_RETRY_COUNT"] = "2"
        os.environ["GROUP_IMAGE_RETRY_DELAY_SEC"] = "0.2"
        os.environ["CHAT_IMAGE_NATS_ENABLED"] = "true"
        os.environ["CHAT_IMAGE_NATS_SERVERS"] = (
            "nats://127.0.0.1:4222,nats://127.0.0.1:4223"
        )
        os.environ["CHAT_IMAGE_NATS_SUBJECT"] = "task.subject"
        os.environ["CHAT_IMAGE_NATS_CLIENT_NAME"] = "collector"
        os.environ["CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC"] = "9"
        os.environ["CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC"] = "7"

        cfg = load_logger_chat_image_config()
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
        self.assertEqual(cfg.nats.client_name, "collector")
        self.assertEqual(cfg.nats.connect_timeout_sec, 9.0)
        self.assertEqual(cfg.nats.publish_timeout_sec, 7.0)


class TestProcessorChatImageConfig(unittest.TestCase):
    _env_backup: dict[str, str] = {}

    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_defaults(self) -> None:
        for key in list(os.environ):
            if key.startswith("CHAT_IMAGE_") or key.startswith("GROUP_IMAGE_"):
                os.environ.pop(key, None)

        cfg = load_processor_chat_image_config()
        self.assertEqual(cfg.save_root, Path("data/chat_images"))
        self.assertFalse(cfg.nats.enabled)
        self.assertEqual(cfg.nats.servers, ("nats://127.0.0.1:4222",))
        self.assertEqual(cfg.nats.subject, "chat.image.tagger.task")
        self.assertEqual(cfg.nats.queue_group, "chat-image-tagger-workers")
        self.assertEqual(cfg.nats.client_name, "data-assistant")
        self.assertEqual(cfg.nats.connect_timeout_sec, 5.0)
        self.assertFalse(cfg.tagger.enabled)
        self.assertFalse(cfg.tagger.auto_run)
        self.assertIsNone(cfg.tagger.base_url)
        self.assertIsNone(cfg.tagger.threshold)
        self.assertIsNone(cfg.tagger.use_chinese_name)
        self.assertIsNone(cfg.tagger.top_k)


if __name__ == "__main__":
    unittest.main()
