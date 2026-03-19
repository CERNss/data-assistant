from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from processor_service.service import main as processor_main


class TestProcessorMainGracefulShutdown(unittest.IsolatedAsyncioTestCase):
    async def test_stops_health_when_worker_finishes_first(self) -> None:
        health_stopped = asyncio.Event()

        async def _fake_health_server(
            host: str = "0.0.0.0",
            port: int = 8080,
            stop_event: asyncio.Event | None = None,
        ) -> None:
            _ = (host, port)
            self.assertIsNotNone(stop_event)
            assert stop_event is not None
            await stop_event.wait()
            health_stopped.set()

        async def _fake_worker(
            process_backlog: bool,
            stop_event: asyncio.Event | None = None,
        ) -> int:
            self.assertTrue(process_backlog)
            self.assertIsNotNone(stop_event)
            return 0

        with (
            patch(
                "processor_service.service.main._install_shutdown_handlers",
                side_effect=lambda _stop_event: None,
            ),
            patch(
                "processor_service.service.main.run_health_server",
                new=_fake_health_server,
            ),
            patch(
                "processor_service.service.main._run_tagger_worker",
                new=_fake_worker,
            ),
        ):
            result = await processor_main._main()

        self.assertEqual(result, 0)
        self.assertTrue(health_stopped.is_set())

    async def test_stops_worker_when_health_exits_first(self) -> None:
        worker_stopped = asyncio.Event()

        async def _fake_health_server(
            host: str = "0.0.0.0",
            port: int = 8080,
            stop_event: asyncio.Event | None = None,
        ) -> None:
            _ = (host, port, stop_event)
            return None

        async def _fake_worker(
            process_backlog: bool,
            stop_event: asyncio.Event | None = None,
        ) -> int:
            self.assertTrue(process_backlog)
            self.assertIsNotNone(stop_event)
            assert stop_event is not None
            await stop_event.wait()
            worker_stopped.set()
            return 7

        with (
            patch(
                "processor_service.service.main._install_shutdown_handlers",
                side_effect=lambda _stop_event: None,
            ),
            patch(
                "processor_service.service.main.run_health_server",
                new=_fake_health_server,
            ),
            patch(
                "processor_service.service.main._run_tagger_worker",
                new=_fake_worker,
            ),
            patch("processor_service.service.main.logger.warning") as logger_warning,
        ):
            result = await processor_main._main()

        self.assertEqual(result, 7)
        self.assertTrue(worker_stopped.is_set())
        logger_warning.assert_called_once_with(
            "Health server exited unexpectedly. Stopping worker..."
        )


if __name__ == "__main__":
    unittest.main()
