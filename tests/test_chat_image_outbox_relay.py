from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from logger_service.service.chat_image.outbox_relay import (
    _decode_payload,
    relay_once,
    run_outbox_relay,
)


def _config(
    *, nats_enabled: bool = True, relay_enabled: bool = True
) -> SimpleNamespace:
    return SimpleNamespace(
        nats=SimpleNamespace(enabled=nats_enabled),
        outbox=SimpleNamespace(
            enabled=relay_enabled,
            interval_sec=30.0,
            batch_size=100,
            max_attempts=0,
            min_age_sec=15.0,
        ),
    )


def _row(payload: object, *, dispatch_id: int = 1, image_id: int = 10) -> dict:
    return {
        "id": dispatch_id,
        "image_id": image_id,
        "subject": "chat.image.tagger.task",
        "payload": payload,
        "attempt_count": 0,
    }


REPO = "logger_service.service.persistence.repository"
RELAY = "logger_service.service.chat_image.outbox_relay"


class TestDecodePayload(unittest.TestCase):
    def test_dict_passthrough(self) -> None:
        self.assertEqual(_decode_payload({"a": 1}), {"a": 1})

    def test_json_string_parsed(self) -> None:
        self.assertEqual(_decode_payload('{"a": 1}'), {"a": 1})

    def test_invalid_json_returns_none(self) -> None:
        self.assertIsNone(_decode_payload("not json {"))

    def test_non_object_json_returns_none(self) -> None:
        self.assertIsNone(_decode_payload("[1, 2]"))

    def test_unsupported_type_returns_none(self) -> None:
        self.assertIsNone(_decode_payload(123))


class TestRelayOnce(unittest.IsolatedAsyncioTestCase):
    async def test_no_rows_does_not_publish(self) -> None:
        with (
            patch(
                f"{REPO}.fetch_unpublished_nats_dispatches",
                new=AsyncMock(return_value=[]),
            ),
            patch(f"{RELAY}.publish_tagger_task_with_result", new=AsyncMock()) as pub,
        ):
            summary = await relay_once(_config())

        self.assertEqual(summary, {"picked": 0, "published": 0, "failed": 0})
        pub.assert_not_awaited()

    async def test_published_row_marked_published_with_msg_id(self) -> None:
        with (
            patch(
                f"{REPO}.fetch_unpublished_nats_dispatches",
                new=AsyncMock(return_value=[_row({"image_id": 10})]),
            ),
            patch(
                f"{RELAY}.publish_tagger_task_with_result",
                new=AsyncMock(return_value=(True, None)),
            ) as pub,
            patch(f"{REPO}.mark_nats_dispatch_published", new=AsyncMock()) as mark_ok,
            patch(f"{REPO}.mark_nats_dispatch_failed", new=AsyncMock()) as mark_bad,
        ):
            summary = await relay_once(_config())

        self.assertEqual(summary, {"picked": 1, "published": 1, "failed": 0})
        mark_ok.assert_awaited_once_with(1)
        mark_bad.assert_not_awaited()
        self.assertEqual(pub.await_args.kwargs["msg_id"], "10")

    async def test_failed_publish_marked_failed(self) -> None:
        with (
            patch(
                f"{REPO}.fetch_unpublished_nats_dispatches",
                new=AsyncMock(return_value=[_row({"image_id": 10})]),
            ),
            patch(
                f"{RELAY}.publish_tagger_task_with_result",
                new=AsyncMock(return_value=(False, "boom")),
            ),
            patch(f"{REPO}.mark_nats_dispatch_published", new=AsyncMock()) as mark_ok,
            patch(f"{REPO}.mark_nats_dispatch_failed", new=AsyncMock()) as mark_bad,
        ):
            summary = await relay_once(_config())

        self.assertEqual(summary, {"picked": 1, "published": 0, "failed": 1})
        mark_ok.assert_not_awaited()
        mark_bad.assert_awaited_once_with(1, error="boom")

    async def test_invalid_payload_failed_without_publish(self) -> None:
        with (
            patch(
                f"{REPO}.fetch_unpublished_nats_dispatches",
                new=AsyncMock(return_value=[_row("not json {")]),
            ),
            patch(f"{RELAY}.publish_tagger_task_with_result", new=AsyncMock()) as pub,
            patch(f"{REPO}.mark_nats_dispatch_published", new=AsyncMock()) as mark_ok,
            patch(f"{REPO}.mark_nats_dispatch_failed", new=AsyncMock()) as mark_bad,
        ):
            summary = await relay_once(_config())

        self.assertEqual(summary, {"picked": 1, "published": 0, "failed": 1})
        pub.assert_not_awaited()
        mark_ok.assert_not_awaited()
        mark_bad.assert_awaited_once_with(1, error="invalid outbox payload")


class TestRunOutboxRelay(unittest.IsolatedAsyncioTestCase):
    async def test_returns_immediately_when_nats_disabled(self) -> None:
        stop_event = asyncio.Event()
        with patch(f"{RELAY}.relay_once", new=AsyncMock()) as relay_mock:
            await run_outbox_relay(_config(nats_enabled=False), stop_event=stop_event)
        relay_mock.assert_not_awaited()

    async def test_returns_immediately_when_relay_disabled(self) -> None:
        stop_event = asyncio.Event()
        with patch(f"{RELAY}.relay_once", new=AsyncMock()) as relay_mock:
            await run_outbox_relay(_config(relay_enabled=False), stop_event=stop_event)
        relay_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
