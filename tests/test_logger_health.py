from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from logger_service.service.napcat.connection import _health_handler


def _make_app() -> web.Application:
    app = web.Application()
    app.router.add_route("GET", "/health", _health_handler)
    return app


class TestLoggerHealthEndpoint(AioHTTPTestCase):
    """Verify the /health handler returns 200 with expected JSON body."""

    async def get_application(self) -> web.Application:
        return _make_app()

    async def test_health_returns_200(self) -> None:
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200)

    async def test_health_returns_json_status_ok(self) -> None:
        resp = await self.client.request("GET", "/health")
        body = await resp.json()
        self.assertEqual(body, {"status": "ok"})

    async def test_health_content_type_is_json(self) -> None:
        resp = await self.client.request("GET", "/health")
        self.assertIn("application/json", resp.content_type)


class TestLoggerHealthDoesNotAffectOtherRoutes(AioHTTPTestCase):
    """Adding /health must not break other routes on the same app."""

    async def get_application(self) -> web.Application:
        app = _make_app()

        async def _dummy_ws(request: web.Request) -> web.WebSocketResponse:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.close()
            return ws

        app.router.add_route("GET", "/onebot/v11/ws", _dummy_ws)
        return app

    async def test_ws_route_still_accessible(self) -> None:
        resp = await self.client.request("GET", "/onebot/v11/ws")
        # WebSocket upgrade returns 101 on proper handshake; without
        # WS headers aiohttp responds 426 (Upgrade Required) or 200.
        # Either way the route exists and is reachable.
        self.assertNotEqual(resp.status, 404)

    async def test_health_still_works_alongside_ws(self) -> None:
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200)


class TestLoggerHealthDbProbe(unittest.IsolatedAsyncioTestCase):
    async def test_returns_503_when_db_probe_fails(self) -> None:
        pool = SimpleNamespace(fetchval=AsyncMock(side_effect=RuntimeError("db down")))
        with patch(
            "logger_service.service.persistence.db.get_pool", return_value=pool
        ):
            resp = await _health_handler(None)
        self.assertEqual(resp.status, 503)

    async def test_returns_200_when_db_probe_ok(self) -> None:
        pool = SimpleNamespace(fetchval=AsyncMock(return_value=1))
        with patch(
            "logger_service.service.persistence.db.get_pool", return_value=pool
        ):
            resp = await _health_handler(None)
        self.assertEqual(resp.status, 200)

    async def test_returns_200_when_pool_uninitialized(self) -> None:
        with patch(
            "logger_service.service.persistence.db.get_pool",
            side_effect=RuntimeError("not initialized"),
        ):
            resp = await _health_handler(None)
        self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
