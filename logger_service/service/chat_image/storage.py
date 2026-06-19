from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"}


def is_image_attachment(content_type: str | None, filename: str | None, url: str | None) -> bool:
    if content_type and content_type.lower().startswith("image/"):
        return True
    if filename and Path(filename).suffix.lower() in IMAGE_EXTENSIONS:
        return True
    if url:
        path = Path(urlparse(url).path)
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return True
    return False


def build_image_save_path(
    *,
    save_root: Path,
    chat_type: str,
    chat_id: str,
    message_id: str,
    attachment_index: int,
    filename: str | None,
    source_url: str | None,
) -> Path:
    image_dir = save_root / chat_type / chat_id
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    original_name = _choose_filename(filename, attachment_index, source_url)
    saved_name = f"{ts}_{message_id}_{attachment_index}_{original_name}"
    return image_dir / saved_name


def _choose_filename(filename: str | None, fallback_index: int, url: str | None) -> str:
    if filename:
        return _safe_filename(filename)
    if url:
        parsed_name = Path(urlparse(url).path).name
        if parsed_name:
            return _safe_filename(parsed_name)
    return f"image_{fallback_index}.bin"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or "image.bin"
