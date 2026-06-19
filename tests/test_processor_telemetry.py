from __future__ import annotations

import importlib
import os
import unittest
from builtins import __import__ as builtins_import
from typing import Any
from unittest.mock import patch


class TestProcessorTelemetry(unittest.TestCase):
    _env_backup: dict[str, str] = {}

    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_init_telemetry_fail_open_on_exporter_error(self) -> None:
        os.environ["OTEL_ENABLED"] = "true"

        telemetry = importlib.import_module("processor_service.service.telemetry")
        telemetry = importlib.reload(telemetry)

        def _import_with_otel_error(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.startswith("opentelemetry"):
                raise ImportError("missing opentelemetry")
            return builtins_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=_import_with_otel_error),
            patch.object(telemetry.loguru_logger, "warning") as warning_mock,
        ):
            telemetry.init_telemetry()

        warning_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
