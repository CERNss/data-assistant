from __future__ import annotations

import sys
import tempfile
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

if "asyncpg" not in sys.modules:
    _asyncpg_stub = types.ModuleType("asyncpg")
    setattr(_asyncpg_stub, "Pool", object)
    setattr(_asyncpg_stub, "Connection", object)
    setattr(_asyncpg_stub, "create_pool", MagicMock())
    setattr(_asyncpg_stub, "connect", AsyncMock())
    sys.modules["asyncpg"] = _asyncpg_stub

from logger_service.service import export


class TestExportCliArgs(unittest.TestCase):
    def test_no_filter_raises_argument_error(self) -> None:
        with self.assertRaises(SystemExit):
            export.parse_args([])

    def test_parse_args_with_user_filter_and_limit(self) -> None:
        args = export.parse_args(
            ["--user-id", "123", "--limit", "5", "--from", "2026-03-01"]
        )
        self.assertEqual(args.user_id, 123)
        self.assertEqual(args.limit, 5)
        self.assertEqual(args.from_time, datetime(2026, 3, 1, 0, 0, tzinfo=UTC))

    def test_build_query_applies_limit_and_order(self) -> None:
        args = export.parse_args(["--group-id", "456", "--limit", "2"])
        query, params = export.build_query(args)
        self.assertIn("ORDER BY event_time ASC", query)
        self.assertIn("LIMIT", query)
        self.assertEqual(params[-1], 2)


class TestExportCliRun(unittest.IsolatedAsyncioTestCase):
    async def test_run_empty_result_writes_zero_byte_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "out.jsonl"

            with patch(
                "logger_service.service.export.fetch_messages",
                new=AsyncMock(return_value=[]),
            ):
                exit_code = await export._run(
                    ["--user-id", "123", "--output", str(output_path)]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
