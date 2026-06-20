from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if "asyncpg" not in sys.modules:
    _asyncpg_stub = types.ModuleType("asyncpg")
    setattr(_asyncpg_stub, "Pool", object)
    setattr(_asyncpg_stub, "Connection", object)
    setattr(_asyncpg_stub, "create_pool", MagicMock())
    sys.modules["asyncpg"] = _asyncpg_stub

from logger_service.service.persistence.config import PostgresConfig
from logger_service.service.persistence.db import init_db


class TestPersistenceDbInit(unittest.IsolatedAsyncioTestCase):
    async def test_init_db_executes_ddl_with_onebot_messages_table(self) -> None:
        conn = AsyncMock()
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__.return_value = conn
        acquire_ctx.__aexit__.return_value = None

        pool = MagicMock()
        pool.acquire.return_value = acquire_ctx

        with patch(
            "logger_service.service.persistence.db.asyncpg.create_pool",
            new=AsyncMock(return_value=pool),
        ):
            await init_db(PostgresConfig(dsn="postgresql://example/test"))

        conn.execute.assert_awaited_once()
        ddl_sql = conn.execute.await_args.args[0]
        self.assertIn("CREATE TABLE IF NOT EXISTS onebot_messages", ddl_sql)
        self.assertIn("idx_onebot_messages_user_id", ddl_sql)
        self.assertIn("idx_onebot_messages_group_id", ddl_sql)
        self.assertIn("idx_onebot_messages_event_time", ddl_sql)


class TestCreatePoolWithRetry(unittest.IsolatedAsyncioTestCase):
    async def test_retries_then_succeeds(self) -> None:
        from logger_service.service.persistence.db import _create_pool_with_retry

        pool = MagicMock()
        create = AsyncMock(side_effect=[OSError("not ready"), pool])
        with (
            patch(
                "logger_service.service.persistence.db.asyncpg.create_pool", new=create
            ),
            patch(
                "logger_service.service.persistence.db.asyncio.sleep", new=AsyncMock()
            ),
        ):
            result = await _create_pool_with_retry(
                PostgresConfig(
                    dsn="postgresql://x",
                    connect_max_attempts=3,
                    connect_retry_delay_sec=0.0,
                )
            )

        self.assertIs(result, pool)
        self.assertEqual(create.await_count, 2)

    async def test_raises_after_max_attempts(self) -> None:
        from logger_service.service.persistence.db import _create_pool_with_retry

        create = AsyncMock(side_effect=OSError("never ready"))
        with (
            patch(
                "logger_service.service.persistence.db.asyncpg.create_pool", new=create
            ),
            patch(
                "logger_service.service.persistence.db.asyncio.sleep", new=AsyncMock()
            ),
        ):
            with self.assertRaises(OSError):
                await _create_pool_with_retry(
                    PostgresConfig(dsn="postgresql://x", connect_max_attempts=2)
                )

        self.assertEqual(create.await_count, 2)


if __name__ == "__main__":
    unittest.main()
