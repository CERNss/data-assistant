from __future__ import annotations

import unittest
from unittest.mock import patch

from processor_service.service import main as processor_main


class TestProcessorMain(unittest.TestCase):
    def test_main_initializes_telemetry_before_worker(self) -> None:
        with (
            patch(
                "processor_service.service.main.telemetry.init_telemetry"
            ) as init_telemetry,
            patch(
                "processor_service.service.main.telemetry.install_error_hooks"
            ) as install_error_hooks,
            patch(
                "processor_service.service.main.run_tagger_worker"
            ) as run_tagger_worker,
        ):
            processor_main.main()

        init_telemetry.assert_called_once_with()
        install_error_hooks.assert_called_once_with()
        run_tagger_worker.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
