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

        cfg = load_chat_image_config()
        self.assertEqual(cfg.save_root, Path("data/chat_images"))
        self.assertEqual(cfg.timeout_sec, 20.0)
        self.assertEqual(cfg.retry_count, 3)
        self.assertEqual(cfg.retry_delay_sec, 0.8)
        self.assertEqual(cfg.audit_log_file, Path("data/group_images.jsonl"))

    def test_overrides(self) -> None:
        os.environ["CHAT_IMAGE_SAVE_DIR"] = "/tmp/chat-images"
        os.environ["GROUP_IMAGE_TIMEOUT_SEC"] = "5"
        os.environ["GROUP_IMAGE_RETRY_COUNT"] = "2"
        os.environ["GROUP_IMAGE_RETRY_DELAY_SEC"] = "0.2"

        cfg = load_chat_image_config()
        self.assertEqual(cfg.save_root, Path("/tmp/chat-images"))
        self.assertEqual(cfg.timeout_sec, 5.0)
        self.assertEqual(cfg.retry_count, 2)
        self.assertEqual(cfg.retry_delay_sec, 0.2)
