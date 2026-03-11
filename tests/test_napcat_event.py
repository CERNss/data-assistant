from __future__ import annotations

import unittest

from data_logger.service.napcat.event import ImageSegment, OneBotEvent, parse_event


# ---------------------------------------------------------------------------
# Shared test payloads
# ---------------------------------------------------------------------------

PRIVATE_TEXT_EVENT: dict[str, object] = {
    "time": 1700000000,
    "self_id": 3755597070,
    "post_type": "message",
    "message_type": "private",
    "sub_type": "friend",
    "message_id": 12345,
    "user_id": 987654321,
    "message": [{"type": "text", "data": {"text": "hello"}}],
    "raw_message": "hello",
    "sender": {"user_id": 987654321, "nickname": "TestUser"},
    "message_format": "array",
}

GROUP_IMAGE_EVENT: dict[str, object] = {
    "time": 1700000001,
    "self_id": 3755597070,
    "post_type": "message",
    "message_type": "group",
    "sub_type": "normal",
    "message_id": 99999,
    "user_id": 111111,
    "group_id": 222222,
    "group_name": "TestGroup",
    "message": [
        {
            "type": "image",
            "data": {
                "file": "abc.image",
                "url": "https://example.com/img.jpg?k=v&amp;x=1",
                "sub_type": 0,
                "file_size": 12345,
                "summary": "[图片]",
            },
        }
    ],
    "raw_message": "[CQ:image,file=abc.image,url=https://example.com/img.jpg?k=v&amp;x=1]",
    "sender": {"user_id": 111111, "nickname": "User", "role": "member"},
    "message_format": "array",
}

CQ_IMAGE_EVENT: dict[str, object] = {
    "time": 1700000002,
    "self_id": 3755597070,
    "post_type": "message",
    "message_type": "private",
    "sub_type": "friend",
    "message_id": 55555,
    "user_id": 333333,
    "message": "[CQ:image,file=test.jpg,url=https://example.com/test.jpg]",
    "raw_message": "[CQ:image,file=test.jpg,url=https://example.com/test.jpg]",
    "sender": {"user_id": 333333},
    "message_format": "string",
}

META_HEARTBEAT_EVENT: dict[str, object] = {
    "time": 1700000003,
    "self_id": 3755597070,
    "post_type": "meta_event",
    "meta_event_type": "heartbeat",
    "status": {"online": True, "good": True},
    "interval": 5000,
}

NOTICE_EVENT: dict[str, object] = {
    "time": 1700000004,
    "self_id": 3755597070,
    "post_type": "notice",
    "notice_type": "group_recall",
    "group_id": 222222,
    "user_id": 111111,
    "message_id": 88888,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseEventPrivateText(unittest.TestCase):
    def test_returns_onebot_event(self) -> None:
        evt = parse_event(PRIVATE_TEXT_EVENT)
        self.assertIsInstance(evt, OneBotEvent)

    def test_basic_fields(self) -> None:
        evt = parse_event(PRIVATE_TEXT_EVENT)
        self.assertEqual(evt.post_type, "message")
        self.assertEqual(evt.time, 1700000000)
        self.assertEqual(evt.self_id, 3755597070)
        self.assertEqual(evt.message_type, "private")
        self.assertEqual(evt.sub_type, "friend")
        self.assertEqual(evt.message_id, "12345")
        self.assertEqual(evt.user_id, 987654321)

    def test_no_images_for_text_message(self) -> None:
        evt = parse_event(PRIVATE_TEXT_EVENT)
        self.assertEqual(evt.images, [])

    def test_message_segments_populated(self) -> None:
        evt = parse_event(PRIVATE_TEXT_EVENT)
        self.assertIsNotNone(evt.message_segments)
        segments = evt.message_segments
        assert segments is not None
        self.assertEqual(len(segments), 1)

    def test_sender_preserved(self) -> None:
        evt = parse_event(PRIVATE_TEXT_EVENT)
        self.assertIsNotNone(evt.sender)
        sender = evt.sender
        assert sender is not None
        self.assertEqual(sender["nickname"], "TestUser")

    def test_group_id_none_for_private(self) -> None:
        evt = parse_event(PRIVATE_TEXT_EVENT)
        self.assertIsNone(evt.group_id)
        self.assertIsNone(evt.group_name)


class TestParseEventGroupImage(unittest.TestCase):
    def test_group_id_and_name(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        self.assertEqual(evt.group_id, 222222)
        self.assertEqual(evt.group_name, "TestGroup")

    def test_images_populated(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        self.assertEqual(len(evt.images), 1)
        img = evt.images[0]
        self.assertIsInstance(img, ImageSegment)

    def test_image_url_raw(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        self.assertEqual(img.url_raw, "https://example.com/img.jpg?k=v&amp;x=1")

    def test_image_url_decoded_html_unescape(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        # &amp; should be unescaped to &
        self.assertEqual(img.url_decoded, "https://example.com/img.jpg?k=v&x=1")

    def test_image_sub_type_is_str(self) -> None:
        # protocol sends int 0; parser normalises to str
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        self.assertIsInstance(img.sub_type, str)
        self.assertEqual(img.sub_type, "0")

    def test_image_file_size(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        self.assertEqual(img.file_size, 12345)

    def test_image_summary(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        self.assertEqual(img.summary, "[图片]")

    def test_image_file_name(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        self.assertEqual(img.file_name, "abc.image")

    def test_image_seq(self) -> None:
        evt = parse_event(GROUP_IMAGE_EVENT)
        img = evt.images[0]
        self.assertEqual(img.seq, 0)


class TestParseEventCQString(unittest.TestCase):
    def test_cq_message_stored(self) -> None:
        evt = parse_event(CQ_IMAGE_EVENT)
        self.assertIsNotNone(evt.message_cq)
        message_cq = evt.message_cq
        assert message_cq is not None
        self.assertIn("CQ:image", message_cq)

    def test_images_extracted_from_cq(self) -> None:
        evt = parse_event(CQ_IMAGE_EVENT)
        self.assertEqual(len(evt.images), 1)

    def test_cq_image_url(self) -> None:
        evt = parse_event(CQ_IMAGE_EVENT)
        img = evt.images[0]
        self.assertEqual(img.url_raw, "https://example.com/test.jpg")
        self.assertEqual(img.url_decoded, "https://example.com/test.jpg")

    def test_cq_image_sub_type_none(self) -> None:
        evt = parse_event(CQ_IMAGE_EVENT)
        img = evt.images[0]
        self.assertIsNone(img.sub_type)

    def test_message_segments_none_for_cq(self) -> None:
        evt = parse_event(CQ_IMAGE_EVENT)
        self.assertIsNone(evt.message_segments)


class TestParseEventMissingFields(unittest.TestCase):
    def _base(self) -> dict[str, object]:
        return {
            "time": 1700000000,
            "self_id": 3755597070,
            "post_type": "message",
        }

    def test_missing_time_raises(self) -> None:
        payload = self._base()
        del payload["time"]
        with self.assertRaises(ValueError):
            parse_event(payload)

    def test_missing_self_id_raises(self) -> None:
        payload = self._base()
        del payload["self_id"]
        with self.assertRaises(ValueError):
            parse_event(payload)

    def test_missing_post_type_raises(self) -> None:
        payload = self._base()
        del payload["post_type"]
        with self.assertRaises(ValueError):
            parse_event(payload)

    def test_empty_post_type_raises(self) -> None:
        payload = self._base()
        payload["post_type"] = ""
        with self.assertRaises(ValueError):
            parse_event(payload)

    def test_invalid_time_raises(self) -> None:
        payload = self._base()
        payload["time"] = "not-a-number"
        with self.assertRaises(ValueError):
            parse_event(payload)

    def test_invalid_self_id_raises(self) -> None:
        payload = self._base()
        payload["self_id"] = "not-a-number"
        with self.assertRaises(ValueError):
            parse_event(payload)


class TestParseEventMetaEvent(unittest.TestCase):
    def test_post_type_meta_event(self) -> None:
        evt = parse_event(META_HEARTBEAT_EVENT)
        self.assertEqual(evt.post_type, "meta_event")

    def test_no_images(self) -> None:
        evt = parse_event(META_HEARTBEAT_EVENT)
        self.assertEqual(evt.images, [])

    def test_no_message_type(self) -> None:
        evt = parse_event(META_HEARTBEAT_EVENT)
        self.assertIsNone(evt.message_type)

    def test_no_message_segments(self) -> None:
        evt = parse_event(META_HEARTBEAT_EVENT)
        self.assertIsNone(evt.message_segments)

    def test_self_id_and_time(self) -> None:
        evt = parse_event(META_HEARTBEAT_EVENT)
        self.assertEqual(evt.self_id, 3755597070)
        self.assertEqual(evt.time, 1700000003)


class TestParseEventNotice(unittest.TestCase):
    def test_post_type_notice(self) -> None:
        evt = parse_event(NOTICE_EVENT)
        self.assertEqual(evt.post_type, "notice")

    def test_no_images(self) -> None:
        evt = parse_event(NOTICE_EVENT)
        self.assertEqual(evt.images, [])

    def test_group_id_extracted(self) -> None:
        evt = parse_event(NOTICE_EVENT)
        self.assertEqual(evt.group_id, 222222)

    def test_user_id_extracted(self) -> None:
        evt = parse_event(NOTICE_EVENT)
        self.assertEqual(evt.user_id, 111111)


if __name__ == "__main__":
    unittest.main()
