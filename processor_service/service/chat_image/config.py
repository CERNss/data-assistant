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


def _env_optional_bool(name: str) -> bool | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def _env_optional_int(name: str, *, minimum: int = 1) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return max(minimum, parsed)


def _env_optional_float(name: str, *, minimum: float = 0.0) -> float | None:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        parsed = float(raw_value)
    except ValueError:
        return None
    return max(minimum, parsed)


@dataclass(frozen=True)
class TaggerPipelineConfig:
    enabled: bool
    auto_run: bool
    drain_interval_sec: float
    healthcheck_path: str
    base_url: str | None
    threshold: float | None
    use_chinese_name: bool | None
    top_k: int | None
    queue_file: Path
    audit_log_file: Path
    batch_size: int
    timeout_sec: float
    max_attempts: int


@dataclass(frozen=True)
class NatsTaskBusConfig:
    enabled: bool
    servers: tuple[str, ...]
    subject: str
    queue_group: str
    client_name: str
    connect_timeout_sec: float
    jetstream_enabled: bool
    stream_name: str
    stream_subjects: tuple[str, ...]
    durable_name: str
    ack_wait_sec: float
    max_deliver: int
    nak_delay_sec: float = 5.0
    stream_max_age_sec: float = 604800.0
    stream_max_bytes: int = -1
    stream_max_msgs: int = -1


@dataclass(frozen=True)
class ChatImageConfig:
    save_root: Path
    nats: NatsTaskBusConfig
    tagger: TaggerPipelineConfig


def load_chat_image_config() -> ChatImageConfig:
    tagger_base_url = os.getenv("CHAT_IMAGE_TAGGER_BASE_URL", "").strip()
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
        nats=NatsTaskBusConfig(
            enabled=_env_bool("CHAT_IMAGE_NATS_ENABLED", False),
            servers=nats_servers or ("nats://127.0.0.1:4222",),
            subject=nats_subject,
            queue_group=os.getenv(
                "CHAT_IMAGE_NATS_QUEUE_GROUP", "chat-image-tagger-workers"
            ).strip()
            or "chat-image-tagger-workers",
            client_name=os.getenv(
                "CHAT_IMAGE_NATS_CLIENT_NAME", "data-assistant"
            ).strip()
            or "data-assistant",
            connect_timeout_sec=_env_float(
                "CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC", 5.0, minimum=0.1
            ),
            jetstream_enabled=_env_bool("CHAT_IMAGE_NATS_JETSTREAM_ENABLED", True),
            stream_name=os.getenv(
                "CHAT_IMAGE_NATS_STREAM", "CHAT_IMAGE_TAGGER_TASKS"
            ).strip()
            or "CHAT_IMAGE_TAGGER_TASKS",
            stream_subjects=stream_subjects,
            durable_name=os.getenv(
                "CHAT_IMAGE_NATS_DURABLE", "chat-image-tagger-workers"
            ).strip()
            or "chat-image-tagger-workers",
            ack_wait_sec=_env_float("CHAT_IMAGE_NATS_ACK_WAIT_SEC", 120.0, minimum=1.0),
            max_deliver=_env_int("CHAT_IMAGE_NATS_MAX_DELIVER", 10, minimum=1),
            nak_delay_sec=_env_float(
                "CHAT_IMAGE_NATS_NAK_DELAY_SEC", 5.0, minimum=0.0
            ),
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
        tagger=TaggerPipelineConfig(
            enabled=_env_bool("CHAT_IMAGE_TAGGER_ENABLED", False),
            auto_run=_env_bool("CHAT_IMAGE_TAGGER_AUTO_RUN", False),
            drain_interval_sec=_env_float(
                "CHAT_IMAGE_TAGGER_DRAIN_INTERVAL_SEC", 10.0, minimum=0.5
            ),
            healthcheck_path=(
                os.getenv("CHAT_IMAGE_TAGGER_HEALTHCHECK_PATH", "/healthz").strip()
                or "/healthz"
            ),
            base_url=tagger_base_url.rstrip("/") or None,
            threshold=_env_optional_float("CHAT_IMAGE_TAGGER_THRESHOLD", minimum=0.0),
            use_chinese_name=_env_optional_bool("CHAT_IMAGE_TAGGER_USE_CHINESE_NAME"),
            top_k=_env_optional_int("CHAT_IMAGE_TAGGER_TOP_K", minimum=1),
            queue_file=Path(
                os.getenv(
                    "CHAT_IMAGE_TAGGER_QUEUE_FILE", "data/chat_image_tagger_queue.json"
                )
            ),
            audit_log_file=Path(
                os.getenv(
                    "CHAT_IMAGE_TAGGER_AUDIT_LOG_FILE", "data/group_image_tags.jsonl"
                )
            ),
            batch_size=_env_int("CHAT_IMAGE_TAGGER_BATCH_SIZE", 16, minimum=1),
            timeout_sec=_env_float(
                "CHAT_IMAGE_TAGGER_TIMEOUT_SEC", 3600.0, minimum=1.0
            ),
            max_attempts=_env_int("CHAT_IMAGE_TAGGER_MAX_ATTEMPTS", 3, minimum=1),
        ),
    )
