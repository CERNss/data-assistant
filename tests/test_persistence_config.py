from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# asyncpg is an optional runtime dep not installed in the test environment.
# Stub it out so that plugins/persistence/__init__.py can be imported without
# a real PostgreSQL driver.
# ---------------------------------------------------------------------------
if "asyncpg" not in sys.modules:
    _asyncpg_stub = types.ModuleType("asyncpg")
    setattr(_asyncpg_stub, "Pool", object)
    setattr(_asyncpg_stub, "Connection", object)
    setattr(_asyncpg_stub, "create_pool", MagicMock())
    sys.modules["asyncpg"] = _asyncpg_stub

from data_logger.service.persistence.config import PostgresConfig, load_postgres_config  # noqa: E402


class TestPostgresConfigDefaults(unittest.TestCase):
    """load_postgres_config() returns correct default DSN when env var not set."""

    _env_backup: dict[str, str] = {}

    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        os.environ.pop("POSTGRES_DSN", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_returns_postgres_config_instance(self) -> None:
        cfg = load_postgres_config()
        self.assertIsInstance(cfg, PostgresConfig)

    def test_default_dsn(self) -> None:
        cfg = load_postgres_config()
        self.assertEqual(cfg.dsn, "postgresql://admin:password@localhost:5432/app_db")


class TestPostgresConfigEnvOverride(unittest.TestCase):
    """load_postgres_config() reads DSN from POSTGRES_DSN env var."""

    _env_backup: dict[str, str] = {}

    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        os.environ.pop("POSTGRES_DSN", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_custom_dsn_from_env(self) -> None:
        custom = "postgresql://user:pass@db.example.com:5432/mydb"
        with patch.dict(os.environ, {"POSTGRES_DSN": custom}):
            cfg = load_postgres_config()
        self.assertEqual(cfg.dsn, custom)

    def test_dsn_whitespace_stripped(self) -> None:
        custom = "  postgresql://user:pass@localhost:5432/testdb  "
        with patch.dict(os.environ, {"POSTGRES_DSN": custom}):
            cfg = load_postgres_config()
        self.assertEqual(cfg.dsn, custom.strip())

    def test_empty_env_uses_empty_string(self) -> None:
        # os.getenv returns "" (not None) when POSTGRES_DSN="", strip() → ""
        with patch.dict(os.environ, {"POSTGRES_DSN": ""}):
            cfg = load_postgres_config()
        self.assertEqual(cfg.dsn, "")


if __name__ == "__main__":
    unittest.main()
