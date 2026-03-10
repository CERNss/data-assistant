from __future__ import annotations

import html
import re
from dataclasses import dataclass


# Matches [CQ:image,...,url=<value>] in raw_message; group(1) = raw URL value.
_CQ_IMAGE_URL_RE = re.compile(r"\[CQ:image,[^\]]*url=([^,\]]+)")


@dataclass
class ImageSegment:
    seq: int  # position in message array (0-based; 0 for CQ fallback)
    url_raw: str | None  # message[].data.url — may contain &amp; HTML entities
    url_decoded: str | None  # html.unescape(url_raw)
    file_name: str | None
    sub_type: str | None  # normalised to str; protocol may send int (0/1)
    file_size: int | None
    summary: str | None
    raw_segment: dict  # full segment dict; synthetic {"_source":"cq_fallback"} for CQ


@dataclass
class OneBotEvent:
    post_type: str  # message / message_sent / notice / request / meta_event
    time: int  # Unix seconds
    self_id: int
    message_type: str | None  # private / group  (message + message_sent only)
    sub_type: str | None
    message_id: str | None  # str-coerced from numeric message_id
    user_id: int | None
    group_id: int | None
    group_name: str | None
    raw_message: str | None
    message_segments: list[dict] | None  # set when message field is an array
    message_cq: str | None  # set when message field is a CQ string
    sender: dict | None
    images: list[ImageSegment]
    raw: dict


def _extract_images_from_segments(segments: list[dict]) -> list[ImageSegment]:
    result: list[ImageSegment] = []
    for seq, seg in enumerate(segments):
        if not isinstance(seg, dict) or seg.get("type") != "image":
            continue
        data = seg.get("data") or {}
        url_raw: str | None = data.get("url") or None
        url_decoded: str | None = html.unescape(url_raw) if url_raw else None
        raw_sub = data.get("sub_type")
        sub_type: str | None = str(raw_sub) if raw_sub is not None else None
        file_size: int | None = None
        try:
            if data.get("file_size") is not None:
                file_size = int(data["file_size"])
        except (ValueError, TypeError):
            pass
        result.append(
            ImageSegment(
                seq=seq,
                url_raw=url_raw,
                url_decoded=url_decoded,
                file_name=data.get("file") or None,
                sub_type=sub_type,
                file_size=file_size,
                summary=data.get("summary") or None,
                raw_segment=seg,
            )
        )
    return result


def _extract_images_from_cq(cq_str: str) -> list[ImageSegment]:
    result: list[ImageSegment] = []
    for seq, match in enumerate(_CQ_IMAGE_URL_RE.finditer(cq_str)):
        url_raw = match.group(1)
        result.append(
            ImageSegment(
                seq=seq,
                url_raw=url_raw,
                url_decoded=html.unescape(url_raw) if url_raw else None,
                file_name=None,
                sub_type=None,
                file_size=None,
                summary=None,
                raw_segment={
                    "type": "image",
                    "data": {"url": url_raw, "_source": "cq_fallback"},
                },
            )
        )
    return result


def parse_event(raw: dict) -> OneBotEvent:
    """Parse raw OneBot11 dict → OneBotEvent.

    Raises ValueError if time, self_id, or post_type are absent or malformed.
    """
    raw_time = raw.get("time")
    if raw_time is None:
        raise ValueError("Missing required field: time")
    try:
        time_val = int(raw_time)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid 'time' value: {raw_time!r}") from exc

    raw_self_id = raw.get("self_id")
    if raw_self_id is None:
        raise ValueError("Missing required field: self_id")
    try:
        self_id_val = int(raw_self_id)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid 'self_id' value: {raw_self_id!r}") from exc

    post_type = raw.get("post_type")
    if not post_type or not isinstance(post_type, str):
        raise ValueError(f"Missing or invalid 'post_type': {post_type!r}")

    message_type: str | None = raw.get("message_type") or None
    sub_type: str | None = raw.get("sub_type") or None

    raw_message_id = raw.get("message_id")
    message_id: str | None = str(raw_message_id) if raw_message_id is not None else None

    user_id: int | None = None
    if raw.get("user_id") is not None:
        try:
            user_id = int(raw["user_id"])
        except (ValueError, TypeError):
            pass

    group_id: int | None = None
    if raw.get("group_id") is not None:
        try:
            group_id = int(raw["group_id"])
        except (ValueError, TypeError):
            pass

    group_name: str | None = raw.get("group_name") or None
    raw_msg_field = raw.get("raw_message")
    raw_message: str | None = raw_msg_field if isinstance(raw_msg_field, str) else None
    sender: dict | None = (
        raw.get("sender") if isinstance(raw.get("sender"), dict) else None
    )

    message_field = raw.get("message")
    message_segments: list[dict] | None = None
    message_cq: str | None = None
    images: list[ImageSegment] = []

    if isinstance(message_field, list):
        message_segments = message_field
        images = _extract_images_from_segments(message_field)
        if not images and raw_message:
            images = _extract_images_from_cq(raw_message)
    elif isinstance(message_field, str):
        message_cq = message_field
        images = _extract_images_from_cq(message_field)
        if not images and raw_message and raw_message != message_field:
            images = _extract_images_from_cq(raw_message)
    elif raw_message:
        images = _extract_images_from_cq(raw_message)

    return OneBotEvent(
        post_type=post_type,
        time=time_val,
        self_id=self_id_val,
        message_type=message_type,
        sub_type=sub_type,
        message_id=message_id,
        user_id=user_id,
        group_id=group_id,
        group_name=group_name,
        raw_message=raw_message,
        message_segments=message_segments,
        message_cq=message_cq,
        sender=sender,
        images=images,
        raw=raw,
    )
