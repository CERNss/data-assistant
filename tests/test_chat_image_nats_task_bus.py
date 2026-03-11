from __future__ import annotations

import json
import unittest

from contracts.chat_image_task import TaskV2, decode_task, encode_task, is_v1_payload


class TestChatImageTaskContract(unittest.TestCase):
    def test_encode_decode_round_trip(self) -> None:
        task = TaskV2(
            version=2,
            image_id=42,
            sha256="abc123",
            source_url="https://example.com/a.png",
            original_url="https://example.com/a.png",
            context={"chat_id": "g1", "message_id": "m1", "seq": 1},
        )
        data = encode_task(task)
        decoded = decode_task(data)
        self.assertEqual(decoded.version, 2)
        self.assertEqual(decoded.image_id, 42)
        self.assertEqual(decoded.sha256, "abc123")
        self.assertEqual(decoded.context["chat_id"], "g1")

    def test_decode_accepts_v1_payload(self) -> None:
        payload = {
            "image_path": "/app/data/chat_images/group/1/test.png",
            "context": {
                "image_id": 99,
                "chat_id": "1",
                "message_id": "100",
                "seq": 0,
                "source_url": "https://example.com/test.png",
                "original_url": "https://example.com/test.png",
            },
        }
        self.assertTrue(is_v1_payload(payload))
        decoded = decode_task(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(decoded.version, 1)
        self.assertEqual(decoded.image_id, 99)
        self.assertEqual(decoded.image_path, "/app/data/chat_images/group/1/test.png")

    def test_decode_rejects_invalid_payload(self) -> None:
        with self.assertRaises(ValueError):
            decode_task(b"[]")
        with self.assertRaises(ValueError):
            decode_task(b'{"context": {}}')


if __name__ == "__main__":
    unittest.main()
