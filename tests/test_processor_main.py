from __future__ import annotations

import unittest
from unittest.mock import patch

from processor_service.service import main as processor_main


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
            processor_main.main()

        init_telemetry.assert_called_once_with()
        install_error_hooks.assert_called_once_with()
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
