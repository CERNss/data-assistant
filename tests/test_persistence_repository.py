from __future__ import annotations

import sys
import types
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

if "asyncpg" not in sys.modules:
    _asyncpg_stub = types.ModuleType("asyncpg")
    setattr(_asyncpg_stub, "Pool", object)
    setattr(_asyncpg_stub, "Connection", object)
    setattr(_asyncpg_stub, "create_pool", MagicMock())
    sys.modules["asyncpg"] = _asyncpg_stub

from logger_service.service.persistence.repository import (
    extract_plain_text,
    extract_sender_fields,
    insert_message,
)


class TestExtractPlainText(unittest.TestCase):
    def test_extracts_text_segments_and_joins(self) -> None:
        segments = [
            {"type": "text", "data": {"text": "hello "}},
            {"type": "image", "data": {"url": "https://example/a.jpg"}},
            {"type": "text", "data": {"text": "world"}},
        ]
        self.assertEqual(
            extract_plain_text(segments, "[CQ:image,url=xx]"), "hello world"
        )

    def test_fallbacks_to_raw_message_when_segments_is_none(self) -> None:
        self.assertEqual(
            extract_plain_text(None, "[CQ:image,file=a.jpg,url=https://example/a.jpg]"),
            "[CQ:image,file=a.jpg,url=https://example/a.jpg]",
        )

    def test_empty_segments_returns_empty_text(self) -> None:
        self.assertEqual(extract_plain_text([], "raw"), "")


class TestExtractSenderFields(unittest.TestCase):
    def test_extracts_sender_fields(self) -> None:
        nickname, card, role = extract_sender_fields(
            {"nickname": "nick", "card": "card", "role": "member"}
        )
        self.assertEqual(nickname, "nick")
        self.assertEqual(card, "card")
        self.assertEqual(role, "member")

    def test_missing_fields_returns_none(self) -> None:
        nickname, card, role = extract_sender_fields({"nickname": "nick"})
        self.assertEqual(nickname, "nick")
        self.assertIsNone(card)
        self.assertIsNone(role)


class TestInsertMessage(unittest.IsolatedAsyncioTestCase):
    async def test_insert_message_writes_structured_row(self) -> None:
        pool = AsyncMock()
        pool.fetchrow.return_value = {"id": 99}

        with patch(
            "logger_service.service.persistence.repository.get_pool",
            return_value=pool,
        ):
            result = await insert_message(
                event_id=10,
                message_type="group",
                user_id=123,
                group_id=456,
                group_name="g",
                sender_nickname="n",
                sender_card="c",
                sender_role="member",
                message_id="m1",
                plain_text="hello",
                message_segments=[{"type": "text", "data": {"text": "hello"}}],
                event_time=datetime(2026, 3, 1, tzinfo=UTC),
            )

        self.assertEqual(result, 99)
        pool.fetchrow.assert_awaited_once()
        sql = pool.fetchrow.await_args.args[0]
        self.assertIn("INSERT INTO onebot_messages", sql)


if __name__ == "__main__":
    unittest.main()
