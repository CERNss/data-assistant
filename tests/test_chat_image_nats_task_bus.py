import unittest
from pathlib import Path

from plugins.chat_image.nats_task_bus import (
    build_tagger_task_payload,
    decode_tagger_task_payload,
    encode_tagger_task_payload,
)


class TestChatImageNatsTaskBus(unittest.TestCase):
    def test_encode_decode_round_trip(self) -> None:
        payload = build_tagger_task_payload(
            image_path=Path("/tmp/a.png"),
            context={"chat_id": "g1", "message_id": "m1"},
        )
        data = encode_tagger_task_payload(payload)
        decoded = decode_tagger_task_payload(data)
        self.assertTrue(decoded["image_path"].endswith("/tmp/a.png"))
        self.assertEqual(decoded["context"]["chat_id"], "g1")

    def test_decode_rejects_invalid_payload(self) -> None:
        with self.assertRaises(ValueError):
            decode_tagger_task_payload(b"[]")
        with self.assertRaises(ValueError):
            decode_tagger_task_payload(b'{"context": {}}')
        with self.assertRaises(ValueError):
            decode_tagger_task_payload(b'{"image_path":"x","context":[]}')
