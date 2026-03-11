from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
class NatsTaskBusConfig:
    enabled: bool
    servers: tuple[str, ...]
    subject: str
    client_name: str
    connect_timeout_sec: float
    publish_timeout_sec: float


@dataclass(frozen=True)
class ChatImageConfig:
    save_root: Path
    timeout_sec: float
    retry_count: int
    retry_delay_sec: float
    audit_log_file: Path
    nats: NatsTaskBusConfig


def load_chat_image_config() -> ChatImageConfig:
    raw_nats_servers = os.getenv("CHAT_IMAGE_NATS_SERVERS", "nats://127.0.0.1:4222")
    nats_servers = tuple(v.strip() for v in raw_nats_servers.split(",") if v.strip())
    return ChatImageConfig(
        save_root=Path(
            os.getenv(
                "CHAT_IMAGE_SAVE_DIR",
                os.getenv("GROUP_IMAGE_SAVE_DIR", "data/chat_images"),
            )
        ),
        timeout_sec=_env_float("GROUP_IMAGE_TIMEOUT_SEC", 20.0, minimum=0.1),
        retry_count=_env_int("GROUP_IMAGE_RETRY_COUNT", 3, minimum=1),
        retry_delay_sec=_env_float("GROUP_IMAGE_RETRY_DELAY_SEC", 0.8, minimum=0.0),
        audit_log_file=Path("data/group_images.jsonl"),
        nats=NatsTaskBusConfig(
            enabled=_env_bool("CHAT_IMAGE_NATS_ENABLED", False),
            servers=nats_servers or ("nats://127.0.0.1:4222",),
            subject=os.getenv(
                "CHAT_IMAGE_NATS_SUBJECT", "chat.image.tagger.task"
            ).strip()
            or "chat.image.tagger.task",
            client_name=os.getenv(
                "CHAT_IMAGE_NATS_CLIENT_NAME", "data-assistant"
            ).strip()
            or "data-assistant",
            connect_timeout_sec=_env_float(
                "CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC", 5.0, minimum=0.1
            ),
            publish_timeout_sec=_env_float(
                "CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC", 3.0, minimum=0.1
            ),
        ),
    )
