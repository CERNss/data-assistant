from __future__ import annotations

import unittest
from unittest.mock import patch

from plugins.napcat.config import NapCatConfig
from plugins.napcat.handler import is_probably_expired_url_error, refresh_image_url


class _FakeActionClient:
    def __init__(self, scripted: dict[str, list[object]]) -> None:
        self._scripted = {key: list(values) for key, values in scripted.items()}

    async def call_action(
        self,
        action: str,
        params: dict | None = None,
        *,
        timeout_sec: float,
    ) -> dict:
        queue = self._scripted.get(action)
        if not queue:
            raise RuntimeError(f"unexpected action: {action}")
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        if not isinstance(result, dict):
            raise RuntimeError(f"invalid scripted result for {action}")
        return result


def _cfg() -> NapCatConfig:
    return NapCatConfig(
        ws_host="0.0.0.0",
        ws_port=3001,
        ws_path="/onebot/v11/ws",
        token="",
        action_timeout_sec=1.0,
        reconnect_sec=5.0,
        heartbeat_timeout_sec=60.0,
        bot_qq=0,
    )


class TestExpiredUrlHeuristic(unittest.TestCase):
    def test_detects_expired_keywords(self) -> None:
        self.assertTrue(is_probably_expired_url_error("status 403 forbidden"))
        self.assertTrue(is_probably_expired_url_error("image rkey expired"))

    def test_non_expired_error(self) -> None:
        self.assertFalse(is_probably_expired_url_error("temporary dns failure"))


class TestRefreshImageUrl(unittest.IsolatedAsyncioTestCase):
    async def test_returns_connection_error_when_no_action_channel(self) -> None:
        with patch("plugins.napcat.handler.get_action_client", return_value=None):
            result = await refresh_image_url("abc.image", _cfg(), message_id="1")

        self.assertIsNone(result.url)
        self.assertEqual(result.final_phase, "error")
        self.assertEqual(len(result.attempts), 1)

    async def test_refresh_succeeds_via_get_image(self) -> None:
        client = _FakeActionClient(
            {
                "nc_get_rkey": [
                    {"status": "ok", "retcode": 0, "data": {"rkey": "abc"}},
                ],
                "get_image": [
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {"url": "https://example.com/a.jpg"},
                    }
                ],
            }
        )

        with patch("plugins.napcat.handler.get_action_client", return_value=client):
            result = await refresh_image_url("abc.image", _cfg(), message_id="2")

        self.assertEqual(result.url, "https://example.com/a.jpg")
        self.assertEqual(result.final_phase, "response")
        actions = [attempt.action for attempt in result.attempts]
        self.assertEqual(actions[0], "nc_get_rkey")
        self.assertEqual(actions[-1], "get_image")

    async def test_refresh_succeeds_via_get_msg(self) -> None:
        client = _FakeActionClient(
            {
                "nc_get_rkey": [{"status": "failed", "retcode": 1, "data": {}}],
                "get_image": [{"status": "failed", "retcode": 1, "data": {}}],
                "get_file": [{"status": "failed", "retcode": 1, "data": {}}],
                "get_msg": [
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {
                            "message": [
                                {
                                    "type": "image",
                                    "data": {"url": "https://example.com/from-msg.jpg"},
                                }
                            ]
                        },
                    }
                ],
            }
        )

        with patch("plugins.napcat.handler.get_action_client", return_value=client):
            result = await refresh_image_url("def.image", _cfg(), message_id="3")

        self.assertEqual(result.url, "https://example.com/from-msg.jpg")
        self.assertEqual(result.final_phase, "response")
        self.assertEqual(result.attempts[-1].action, "get_msg")

    async def test_refresh_chain_exhausted(self) -> None:
        client = _FakeActionClient(
            {
                "nc_get_rkey": [RuntimeError("rkey failed")],
                "get_image": [RuntimeError("get_image failed")],
                "get_file": [RuntimeError("get_file failed")],
                "get_msg": [RuntimeError("get_msg failed")],
            }
        )

        with patch("plugins.napcat.handler.get_action_client", return_value=client):
            result = await refresh_image_url("xyz.image", _cfg(), message_id="4")

        self.assertIsNone(result.url)
        self.assertEqual(result.final_phase, "error")
        self.assertEqual(result.error, "refresh_chain_exhausted")
        self.assertGreaterEqual(len(result.attempts), 4)


if __name__ == "__main__":
    unittest.main()
