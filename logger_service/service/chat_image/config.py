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
    jetstream_enabled: bool
    stream_name: str
    stream_subjects: tuple[str, ...]
    stream_max_age_sec: float = 604800.0
    stream_max_bytes: int = -1
    stream_max_msgs: int = -1


@dataclass(frozen=True)
class OutboxRelayConfig:
    enabled: bool
    interval_sec: float
    batch_size: int
    max_attempts: int
    min_age_sec: float


@dataclass(frozen=True)
class ChatImageConfig:
    save_root: Path
    timeout_sec: float
    retry_count: int
    retry_delay_sec: float
    audit_log_file: Path
    nats: NatsTaskBusConfig
    outbox: OutboxRelayConfig


def load_chat_image_config() -> ChatImageConfig:
    raw_nats_servers = os.getenv("CHAT_IMAGE_NATS_SERVERS", "nats://127.0.0.1:4222")
    nats_servers = tuple(v.strip() for v in raw_nats_servers.split(",") if v.strip())
    nats_subject = (
        os.getenv("CHAT_IMAGE_NATS_SUBJECT", "chat.image.tagger.task").strip()
        or "chat.image.tagger.task"
    )
    raw_stream_subjects = tuple(
        v.strip()
        for v in os.getenv("CHAT_IMAGE_NATS_STREAM_SUBJECTS", "").split(",")
        if v.strip()
    )
    stream_subjects = raw_stream_subjects or (nats_subject,)
    if nats_subject not in stream_subjects:
        stream_subjects = (nats_subject, *stream_subjects)
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
            subject=nats_subject,
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
            jetstream_enabled=_env_bool("CHAT_IMAGE_NATS_JETSTREAM_ENABLED", True),
            stream_name=os.getenv(
                "CHAT_IMAGE_NATS_STREAM", "CHAT_IMAGE_TAGGER_TASKS"
            ).strip()
            or "CHAT_IMAGE_TAGGER_TASKS",
            stream_subjects=stream_subjects,
            stream_max_age_sec=_env_float(
                "CHAT_IMAGE_NATS_STREAM_MAX_AGE_SEC", 604800.0, minimum=0.0
            ),
            stream_max_bytes=_env_int(
                "CHAT_IMAGE_NATS_STREAM_MAX_BYTES", -1, minimum=-1
            ),
            stream_max_msgs=_env_int(
                "CHAT_IMAGE_NATS_STREAM_MAX_MSGS", -1, minimum=-1
            ),
        ),
        outbox=OutboxRelayConfig(
            enabled=_env_bool("CHAT_IMAGE_NATS_OUTBOX_RELAY_ENABLED", True),
            interval_sec=_env_float(
                "CHAT_IMAGE_NATS_OUTBOX_RELAY_INTERVAL_SEC", 30.0, minimum=1.0
            ),
            batch_size=_env_int(
                "CHAT_IMAGE_NATS_OUTBOX_RELAY_BATCH_SIZE", 100, minimum=1
            ),
            max_attempts=_env_int(
                "CHAT_IMAGE_NATS_OUTBOX_MAX_ATTEMPTS", 0, minimum=0
            ),
            min_age_sec=_env_float(
                "CHAT_IMAGE_NATS_OUTBOX_MIN_AGE_SEC", 15.0, minimum=0.0
            ),
        ),
    )
