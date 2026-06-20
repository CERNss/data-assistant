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


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
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
class PostgresConfig:
    dsn: str
    command_timeout_sec: float = 30.0
    connect_max_attempts: int = 30
    connect_retry_delay_sec: float = 2.0
    pool_min_size: int = 2
    pool_max_size: int = 10


def load_postgres_config() -> PostgresConfig:
    return PostgresConfig(
        dsn=os.getenv(
            "POSTGRES_DSN", "postgresql://admin:password@localhost:5432/app_db"
        ).strip(),
        command_timeout_sec=_env_float(
            "POSTGRES_COMMAND_TIMEOUT_SEC", 30.0, minimum=0.0
        ),
        connect_max_attempts=_env_int(
            "POSTGRES_CONNECT_MAX_ATTEMPTS", 30, minimum=1
        ),
        connect_retry_delay_sec=_env_float(
            "POSTGRES_CONNECT_RETRY_DELAY_SEC", 2.0, minimum=0.1
        ),
        pool_min_size=_env_int("POSTGRES_POOL_MIN_SIZE", 2, minimum=1),
        pool_max_size=_env_int("POSTGRES_POOL_MAX_SIZE", 10, minimum=1),
    )
