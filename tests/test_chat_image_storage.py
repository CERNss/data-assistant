import unittest
from pathlib import Path

from plugins.chat_image.storage import build_image_save_path, is_image_attachment


class TestChatImageStorage(unittest.TestCase):
    def test_is_image_attachment(self) -> None:
        self.assertTrue(is_image_attachment("image/png", None, None))
        self.assertTrue(is_image_attachment(None, "photo.JPG", None))
        self.assertTrue(is_image_attachment(None, None, "https://x/y/z.webp"))
        self.assertFalse(is_image_attachment("application/pdf", "a.pdf", "https://x/y/z.pdf"))

    def test_build_image_save_path(self) -> None:
        path = build_image_save_path(
            save_root=Path("/tmp/chat-images"),
            chat_type="group",
            chat_id="group123",
            message_id="msg456",
            attachment_index=2,
            filename="hello.png",
            source_url=None,
        )
        self.assertTrue(str(path).startswith("/tmp/chat-images/group/group123/"))
        self.assertTrue(str(path).endswith("_msg456_2_hello.png") or "msg456_2_hello.png" in str(path))
