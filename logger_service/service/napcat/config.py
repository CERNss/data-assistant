from __future__ import annotations

import os
from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return max(minimum, parsed)


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = float(raw_value)
    except ValueError:
        return default
    return max(minimum, parsed)


@dataclass(frozen=True)
class NapCatConfig:
    ws_host: str
    ws_port: int
    ws_path: str
    token: str
    action_timeout_sec: float
    reconnect_sec: float
    heartbeat_timeout_sec: float
    bot_qq: int


def load_napcat_config() -> NapCatConfig:
    return NapCatConfig(
        ws_host=os.getenv("NAPCAT_WS_HOST", "0.0.0.0").strip() or "0.0.0.0",
        ws_port=_env_int("NAPCAT_WS_PORT", 8082, minimum=1),
        ws_path=os.getenv("NAPCAT_WS_PATH", "/onebot/v11/ws").strip()
        or "/onebot/v11/ws",
        token=os.getenv("NAPCAT_TOKEN", "").strip(),
        action_timeout_sec=_env_float("NAPCAT_ACTION_TIMEOUT_SEC", 8.0, minimum=0.1),
        reconnect_sec=_env_float("NAPCAT_RECONNECT_SEC", 5.0, minimum=0.0),
        heartbeat_timeout_sec=_env_float(
            "NAPCAT_HEARTBEAT_TIMEOUT_SEC", 60.0, minimum=0.0
        ),
        bot_qq=_env_int("NAPCAT_BOT_QQ", 0, minimum=0),
    )
