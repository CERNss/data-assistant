from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import sys
import types

if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")

    class _Pool:
        pass

    async def _create_pool(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("create_pool should be mocked in tests")

    asyncpg_stub.Pool = _Pool
    asyncpg_stub.create_pool = _create_pool
    sys.modules["asyncpg"] = asyncpg_stub

from logger_service.service import main as logger_main


class TestLoggerMainGracefulShutdown(unittest.IsolatedAsyncioTestCase):
    async def test_main_passes_stop_event_and_closes_resources(self) -> None:
        napcat_config = SimpleNamespace(
            ws_host="0.0.0.0",
            ws_port=8082,
            ws_path="/onebot/v11/ws",
        )
        pg_config = SimpleNamespace(dsn="postgresql://localhost/test")
        run_server_mock = AsyncMock()

        with (
            patch("logger_service.service.main.telemetry.init_telemetry"),
            patch("logger_service.service.main.telemetry.install_error_hooks"),
            patch(
                "logger_service.service.main._install_shutdown_handlers",
                side_effect=lambda _stop_event: None,
            ),
            patch(
                "logger_service.service.main.load_napcat_config",
                return_value=napcat_config,
            ),
            patch(
                "logger_service.service.main.load_postgres_config",
                return_value=pg_config,
            ),
            patch(
                "logger_service.service.main.init_db",
                new_callable=AsyncMock,
            ) as init_db,
            patch(
                "logger_service.service.main.run_server",
                new=run_server_mock,
            ),
            patch(
                "logger_service.service.main.close_nats_publisher",
                new_callable=AsyncMock,
            ) as close_nats_publisher,
            patch(
                "logger_service.service.main.close_db",
                new_callable=AsyncMock,
            ) as close_db,
        ):
            await logger_main.main()

        init_db.assert_awaited_once_with(pg_config)
        run_server_mock.assert_awaited_once()
        call_args = run_server_mock.await_args
        self.assertEqual(call_args.args[0], napcat_config)
        self.assertEqual(call_args.kwargs["on_event"], logger_main._on_event)
        self.assertIsInstance(call_args.kwargs["stop_event"], asyncio.Event)
        close_nats_publisher.assert_awaited_once_with()
        close_db.assert_awaited_once_with()

    async def test_main_closes_resources_when_server_raises(self) -> None:
        napcat_config = SimpleNamespace(
            ws_host="0.0.0.0",
            ws_port=8082,
            ws_path="/onebot/v11/ws",
        )
        pg_config = SimpleNamespace(dsn="postgresql://localhost/test")
        run_server_mock = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch("logger_service.service.main.telemetry.init_telemetry"),
            patch("logger_service.service.main.telemetry.install_error_hooks"),
            patch(
                "logger_service.service.main._install_shutdown_handlers",
                side_effect=lambda _stop_event: None,
            ),
            patch(
                "logger_service.service.main.load_napcat_config",
                return_value=napcat_config,
            ),
            patch(
                "logger_service.service.main.load_postgres_config",
                return_value=pg_config,
            ),
            patch(
                "logger_service.service.main.init_db",
                new_callable=AsyncMock,
            ),
            patch(
                "logger_service.service.main.run_server",
                new=run_server_mock,
            ),
            patch(
                "logger_service.service.main.close_nats_publisher",
                new_callable=AsyncMock,
            ) as close_nats_publisher,
            patch(
                "logger_service.service.main.close_db",
                new_callable=AsyncMock,
            ) as close_db,
        ):
            with self.assertRaises(RuntimeError):
                await logger_main.main()

        close_nats_publisher.assert_awaited_once_with()
        close_db.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
