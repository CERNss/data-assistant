from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChatImageConfig:
    save_root: Path
    timeout_sec: float
    retry_count: int
    retry_delay_sec: float
    audit_log_file: Path


def load_chat_image_config() -> ChatImageConfig:
    return ChatImageConfig(
        save_root=Path(
            os.getenv("CHAT_IMAGE_SAVE_DIR", os.getenv("GROUP_IMAGE_SAVE_DIR", "data/chat_images"))
        ),
        timeout_sec=float(os.getenv("GROUP_IMAGE_TIMEOUT_SEC", "20")),
        retry_count=int(os.getenv("GROUP_IMAGE_RETRY_COUNT", "3")),
        retry_delay_sec=float(os.getenv("GROUP_IMAGE_RETRY_DELAY_SEC", "0.8")),
        audit_log_file=Path("data/group_images.jsonl"),
    )
