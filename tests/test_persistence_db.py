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


if __name__ == "__main__":
    unittest.main()
