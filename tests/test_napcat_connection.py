from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp

from logger_service.service.napcat.connection import _consume_ws_messages


def _text(data: str) -> SimpleNamespace:
    return SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=data)


def _close() -> SimpleNamespace:
    return SimpleNamespace(type=aiohttp.WSMsgType.CLOSE, data=None)


class _FakeWS:
    """Minimal stand-in for aiohttp WebSocketResponse used by the read loop."""

    def __init__(
        self, messages: list[SimpleNamespace], *, timeout_first: bool = False
    ) -> None:
        self._messages = list(messages)
        self._timeout_first = timeout_first
        self.closed = False
        self.close_calls = 0

    async def receive(self, timeout: float | None = None) -> SimpleNamespace:
        if self._timeout_first:
            self._timeout_first = False
            raise asyncio.TimeoutError
        if not self._messages:
            return SimpleNamespace(type=aiohttp.WSMsgType.CLOSED, data=None)
        return self._messages.pop(0)

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True

    def exception(self) -> Exception:
        return RuntimeError("boom")


class TestConsumeWsMessages(unittest.IsolatedAsyncioTestCase):
    async def test_heartbeat_timeout_closes_stale_connection(self) -> None:
        ws = _FakeWS([], timeout_first=True)
        on_event = AsyncMock()
        action_client = SimpleNamespace(consume_action_response=lambda _raw: False)

        with patch(
            "logger_service.service.napcat.connection.logger.warning"
        ) as warn:
            await _consume_ws_messages(
                ws,
                on_event=on_event,
                action_client=action_client,
                heartbeat_timeout=0.5,
                remote="1.2.3.4",
            )

        self.assertEqual(ws.close_calls, 1)
        on_event.assert_not_awaited()
        warn.assert_called_once()

    async def test_text_message_dispatched_to_on_event(self) -> None:
        ws = _FakeWS([_text('{"post_type": "message"}'), _close()])
        on_event = AsyncMock()
        action_client = SimpleNamespace(consume_action_response=lambda _raw: False)

        await _consume_ws_messages(
            ws,
            on_event=on_event,
            action_client=action_client,
            heartbeat_timeout=None,
            remote="1.2.3.4",
        )

        on_event.assert_awaited_once_with({"post_type": "message"})

    async def test_action_response_not_dispatched_to_on_event(self) -> None:
        ws = _FakeWS([_text('{"echo": "rpc_1"}'), _close()])
        on_event = AsyncMock()
        action_client = SimpleNamespace(consume_action_response=lambda _raw: True)

        await _consume_ws_messages(
            ws,
            on_event=on_event,
            action_client=action_client,
            heartbeat_timeout=None,
            remote="1.2.3.4",
        )

        on_event.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
