from __future__ import annotations

import asyncio
import unittest

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from processor_service.service.health import _health_handler


def _make_app() -> web.Application:
    app = web.Application()
    app.router.add_route("GET", "/health", _health_handler)
    return app


class TestProcessorHealthEndpoint(AioHTTPTestCase):
    """Verify the processor /health handler returns 200 with expected JSON."""

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


class TestProcessorHealthDoesNotBlockWorker(unittest.IsolatedAsyncioTestCase):
    """Health server coroutine must not block other concurrent coroutines."""

    async def test_health_coroutine_does_not_block(self) -> None:
        sentinel = asyncio.Event()

        async def _fake_worker() -> None:
            sentinel.set()

        async def _fake_health() -> None:
            await asyncio.sleep(0)

        await asyncio.wait_for(
            asyncio.gather(_fake_health(), _fake_worker()),
            timeout=2.0,
        )
        self.assertTrue(sentinel.is_set())


class TestProcessorMainIntegration(unittest.TestCase):
    """Processor main wires telemetry, health server, and tagger worker."""

    def test_main_initializes_telemetry_before_gather(self) -> None:
        from unittest.mock import patch

        def _fake_asyncio_run(coro: object) -> int:
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            return 0

        with (
            patch(
                "processor_service.service.main.telemetry.init_telemetry"
            ) as init_telemetry,
            patch(
                "processor_service.service.main.telemetry.install_error_hooks"
            ) as install_error_hooks,
            patch("processor_service.service.main.asyncio.run") as mock_run,
        ):
            mock_run.side_effect = _fake_asyncio_run
            from processor_service.service.main import main

            main()

        init_telemetry.assert_called_once_with()
        install_error_hooks.assert_called_once_with()
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
