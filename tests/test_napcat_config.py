from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from plugins.napcat.config import NapCatConfig, load_napcat_config


class TestNapCatConfigDefaults(unittest.TestCase):
    """load_napcat_config() returns correct defaults when no env vars set."""

    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        # Remove all NAPCAT_* vars so defaults apply cleanly
        for key in list(os.environ):
            if key.startswith("NAPCAT_"):
                del os.environ[key]

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_returns_napcat_config_instance(self) -> None:
        cfg = load_napcat_config()
        self.assertIsInstance(cfg, NapCatConfig)

    def test_default_ws_host(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.ws_host, "0.0.0.0")

    def test_default_ws_port(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.ws_port, 3001)

    def test_default_ws_path(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.ws_path, "/onebot/v11/ws")

    def test_default_token_empty(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.token, "")

    def test_default_action_timeout_sec(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.action_timeout_sec, 8.0)

    def test_default_bot_qq_zero(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.bot_qq, 0)

    def test_default_reconnect_sec(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.reconnect_sec, 5.0)

    def test_default_heartbeat_timeout_sec(self) -> None:
        cfg = load_napcat_config()
        self.assertEqual(cfg.heartbeat_timeout_sec, 60.0)


class TestNapCatConfigEnvOverrides(unittest.TestCase):
    """load_napcat_config() picks up env var overrides correctly."""

    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        for key in list(os.environ):
            if key.startswith("NAPCAT_"):
                del os.environ[key]

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_ws_port_parsed_as_int(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_WS_PORT": "8080"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.ws_port, 8080)
        self.assertIsInstance(cfg.ws_port, int)

    def test_ws_host_override(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_WS_HOST": "127.0.0.1"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.ws_host, "127.0.0.1")

    def test_token_override(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_TOKEN": "my-secret-token"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.token, "my-secret-token")

    def test_action_timeout_override(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_ACTION_TIMEOUT_SEC": "15.5"}):
            cfg = load_napcat_config()
        self.assertAlmostEqual(cfg.action_timeout_sec, 15.5)

    def test_bot_qq_parsed_as_int(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_BOT_QQ": "3755597070"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.bot_qq, 3755597070)
        self.assertIsInstance(cfg.bot_qq, int)

    def test_ws_path_override(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_WS_PATH": "/custom/ws"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.ws_path, "/custom/ws")

    def test_reconnect_sec_override(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_RECONNECT_SEC": "10.5"}):
            cfg = load_napcat_config()
        self.assertAlmostEqual(cfg.reconnect_sec, 10.5)

    def test_heartbeat_timeout_sec_override(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_HEARTBEAT_TIMEOUT_SEC": "30.0"}):
            cfg = load_napcat_config()
        self.assertAlmostEqual(cfg.heartbeat_timeout_sec, 30.0)

    def test_invalid_ws_port_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_WS_PORT": "not-a-number"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.ws_port, 3001)

    def test_invalid_bot_qq_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_BOT_QQ": "not-a-number"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.bot_qq, 0)

    def test_invalid_action_timeout_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"NAPCAT_ACTION_TIMEOUT_SEC": "oops"}):
            cfg = load_napcat_config()
        self.assertEqual(cfg.action_timeout_sec, 8.0)


if __name__ == "__main__":
    unittest.main()
