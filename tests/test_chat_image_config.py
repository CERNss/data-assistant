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
        os.environ.pop("CHAT_IMAGE_NATS_JETSTREAM_ENABLED", None)
        os.environ.pop("CHAT_IMAGE_NATS_STREAM", None)
        os.environ.pop("CHAT_IMAGE_NATS_STREAM_SUBJECTS", None)

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
        self.assertTrue(cfg.nats.jetstream_enabled)
        self.assertEqual(cfg.nats.stream_name, "CHAT_IMAGE_TAGGER_TASKS")
        self.assertEqual(cfg.nats.stream_subjects, ("chat.image.tagger.task",))

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
        os.environ["CHAT_IMAGE_NATS_JETSTREAM_ENABLED"] = "false"
        os.environ["CHAT_IMAGE_NATS_STREAM"] = "CUSTOM_STREAM"
        os.environ["CHAT_IMAGE_NATS_STREAM_SUBJECTS"] = "extra.subject"

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
        self.assertFalse(cfg.nats.jetstream_enabled)
        self.assertEqual(cfg.nats.stream_name, "CUSTOM_STREAM")
        self.assertEqual(cfg.nats.stream_subjects, ("task.subject", "extra.subject"))


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
        self.assertTrue(cfg.nats.jetstream_enabled)
        self.assertEqual(cfg.nats.stream_name, "CHAT_IMAGE_TAGGER_TASKS")
        self.assertEqual(cfg.nats.stream_subjects, ("chat.image.tagger.task",))
        self.assertEqual(cfg.nats.durable_name, "chat-image-tagger-workers")
        self.assertEqual(cfg.nats.ack_wait_sec, 120.0)
        self.assertEqual(cfg.nats.max_deliver, 10)
        self.assertFalse(cfg.tagger.enabled)
        self.assertFalse(cfg.tagger.auto_run)
        self.assertEqual(cfg.tagger.drain_interval_sec, 10.0)
        self.assertEqual(cfg.tagger.healthcheck_path, "/healthz")
        self.assertIsNone(cfg.tagger.base_url)
        self.assertIsNone(cfg.tagger.threshold)
        self.assertIsNone(cfg.tagger.use_chinese_name)
        self.assertIsNone(cfg.tagger.top_k)

    def test_overrides(self) -> None:
        for key in list(os.environ):
            if key.startswith("CHAT_IMAGE_") or key.startswith("GROUP_IMAGE_"):
                os.environ.pop(key, None)
        os.environ["CHAT_IMAGE_SAVE_DIR"] = "/tmp/chat-images"
        os.environ["CHAT_IMAGE_NATS_ENABLED"] = "true"
        os.environ["CHAT_IMAGE_NATS_SERVERS"] = (
            "nats://127.0.0.1:4222,nats://127.0.0.1:4223"
        )
        os.environ["CHAT_IMAGE_NATS_SUBJECT"] = "task.subject"
        os.environ["CHAT_IMAGE_NATS_QUEUE_GROUP"] = "workers"
        os.environ["CHAT_IMAGE_NATS_CLIENT_NAME"] = "processor"
        os.environ["CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC"] = "8"
        os.environ["CHAT_IMAGE_NATS_JETSTREAM_ENABLED"] = "false"
        os.environ["CHAT_IMAGE_NATS_STREAM"] = "CUSTOM_STREAM"
        os.environ["CHAT_IMAGE_NATS_STREAM_SUBJECTS"] = "extra.subject"
        os.environ["CHAT_IMAGE_NATS_DURABLE"] = "durable-worker"
        os.environ["CHAT_IMAGE_NATS_ACK_WAIT_SEC"] = "60"
        os.environ["CHAT_IMAGE_NATS_MAX_DELIVER"] = "7"
        os.environ["CHAT_IMAGE_TAGGER_ENABLED"] = "true"
        os.environ["CHAT_IMAGE_TAGGER_AUTO_RUN"] = "true"
        os.environ["CHAT_IMAGE_TAGGER_DRAIN_INTERVAL_SEC"] = "2"
        os.environ["CHAT_IMAGE_TAGGER_HEALTHCHECK_PATH"] = "healthz"
        os.environ["CHAT_IMAGE_TAGGER_BASE_URL"] = "http://tagger:8000/"
        os.environ["CHAT_IMAGE_TAGGER_THRESHOLD"] = "0.7"
        os.environ["CHAT_IMAGE_TAGGER_USE_CHINESE_NAME"] = "false"
        os.environ["CHAT_IMAGE_TAGGER_TOP_K"] = "12"
        os.environ["CHAT_IMAGE_TAGGER_QUEUE_FILE"] = "/tmp/queue.json"
        os.environ["CHAT_IMAGE_TAGGER_AUDIT_LOG_FILE"] = "/tmp/tags.jsonl"
        os.environ["CHAT_IMAGE_TAGGER_BATCH_SIZE"] = "6"
        os.environ["CHAT_IMAGE_TAGGER_TIMEOUT_SEC"] = "30"
        os.environ["CHAT_IMAGE_TAGGER_MAX_ATTEMPTS"] = "4"

        cfg = load_processor_chat_image_config()

        self.assertEqual(cfg.save_root, Path("/tmp/chat-images"))
        self.assertTrue(cfg.nats.enabled)
        self.assertEqual(
            cfg.nats.servers,
            ("nats://127.0.0.1:4222", "nats://127.0.0.1:4223"),
        )
        self.assertEqual(cfg.nats.subject, "task.subject")
        self.assertEqual(cfg.nats.queue_group, "workers")
        self.assertEqual(cfg.nats.client_name, "processor")
        self.assertEqual(cfg.nats.connect_timeout_sec, 8.0)
        self.assertFalse(cfg.nats.jetstream_enabled)
        self.assertEqual(cfg.nats.stream_name, "CUSTOM_STREAM")
        self.assertEqual(cfg.nats.stream_subjects, ("task.subject", "extra.subject"))
        self.assertEqual(cfg.nats.durable_name, "durable-worker")
        self.assertEqual(cfg.nats.ack_wait_sec, 60.0)
        self.assertEqual(cfg.nats.max_deliver, 7)
        self.assertTrue(cfg.tagger.enabled)
        self.assertTrue(cfg.tagger.auto_run)
        self.assertEqual(cfg.tagger.drain_interval_sec, 2.0)
        self.assertEqual(cfg.tagger.healthcheck_path, "healthz")
        self.assertEqual(cfg.tagger.base_url, "http://tagger:8000")
        self.assertEqual(cfg.tagger.threshold, 0.7)
        self.assertFalse(cfg.tagger.use_chinese_name)
        self.assertEqual(cfg.tagger.top_k, 12)
        self.assertEqual(cfg.tagger.queue_file, Path("/tmp/queue.json"))
        self.assertEqual(cfg.tagger.audit_log_file, Path("/tmp/tags.jsonl"))
        self.assertEqual(cfg.tagger.batch_size, 6)
        self.assertEqual(cfg.tagger.timeout_sec, 30.0)
        self.assertEqual(cfg.tagger.max_attempts, 4)


if __name__ == "__main__":
    unittest.main()
