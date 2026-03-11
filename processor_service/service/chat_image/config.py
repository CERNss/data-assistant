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
class TaggerPipelineConfig:
    enabled: bool
    auto_run: bool
    python_bin: str
    tool_root: Path | None
    entry_script: Path
    config_file: Path | None
    queue_file: Path
    run_root: Path
    audit_log_file: Path
    batch_size: int
    timeout_sec: float
    max_attempts: int
    keep_run_artifacts: bool


@dataclass(frozen=True)
class NatsTaskBusConfig:
    enabled: bool
    servers: tuple[str, ...]
    subject: str
    queue_group: str
    client_name: str
    connect_timeout_sec: float


@dataclass(frozen=True)
class ChatImageConfig:
    save_root: Path
    nats: NatsTaskBusConfig
    tagger: TaggerPipelineConfig


def load_chat_image_config() -> ChatImageConfig:
    tagger_tool_root = os.getenv("CHAT_IMAGE_TAGGER_TOOL_ROOT", "").strip()
    tagger_config = os.getenv("CHAT_IMAGE_TAGGER_CONFIG", "config.ini").strip()
    raw_nats_servers = os.getenv("CHAT_IMAGE_NATS_SERVERS", "nats://127.0.0.1:4222")
    nats_servers = tuple(v.strip() for v in raw_nats_servers.split(",") if v.strip())
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
            subject=os.getenv(
                "CHAT_IMAGE_NATS_SUBJECT", "chat.image.tagger.task"
            ).strip()
            or "chat.image.tagger.task",
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
        ),
        tagger=TaggerPipelineConfig(
            enabled=_env_bool("CHAT_IMAGE_TAGGER_ENABLED", False),
            auto_run=_env_bool("CHAT_IMAGE_TAGGER_AUTO_RUN", False),
            python_bin=os.getenv("CHAT_IMAGE_TAGGER_PYTHON", "python").strip()
            or "python",
            tool_root=Path(tagger_tool_root).expanduser() if tagger_tool_root else None,
            entry_script=Path(os.getenv("CHAT_IMAGE_TAGGER_ENTRY_SCRIPT", "main.py")),
            config_file=Path(tagger_config) if tagger_config else None,
            queue_file=Path(
                os.getenv(
                    "CHAT_IMAGE_TAGGER_QUEUE_FILE", "data/chat_image_tagger_queue.json"
                )
            ),
            run_root=Path(
                os.getenv("CHAT_IMAGE_TAGGER_RUN_ROOT", "data/chat_image_tagger_runs")
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
            keep_run_artifacts=_env_bool("CHAT_IMAGE_TAGGER_KEEP_RUN_ARTIFACTS", False),
        ),
    )
