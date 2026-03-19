from __future__ import annotations

import unittest
from unittest.mock import patch

from processor_service.service import main as processor_main


def _fake_asyncio_run(coro: object) -> int:
    close = getattr(coro, "close", None)
    if callable(close):
        close()
    return 0


def _fake_asyncio_run_nonzero(coro: object) -> int:
    close = getattr(coro, "close", None)
    if callable(close):
        close()
    return 3


class TestProcessorMain(unittest.TestCase):
    def test_main_initializes_telemetry_before_run(self) -> None:
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
            processor_main.main()

        init_telemetry.assert_called_once_with()
        install_error_hooks.assert_called_once_with()
        mock_run.assert_called_once()

    def test_main_exits_with_worker_status_when_non_zero(self) -> None:
        with (
            patch("processor_service.service.main.telemetry.init_telemetry"),
            patch("processor_service.service.main.telemetry.install_error_hooks"),
            patch("processor_service.service.main.asyncio.run") as mock_run,
        ):
            mock_run.side_effect = _fake_asyncio_run_nonzero
            with self.assertRaises(SystemExit) as ctx:
                processor_main.main()

        self.assertEqual(ctx.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
