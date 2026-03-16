from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .db import get_pool


def extract_plain_text(
    segments: list[dict[str, Any]] | None,
    raw_message: str | None,
) -> str | None:
    if segments is None:
        return raw_message

    parts: list[str] = []
    for segment in segments:
        if not isinstance(segment, dict) or segment.get("type") != "text":
            continue
        data = segment.get("data")
        if not isinstance(data, dict):
            continue
        text = data.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def extract_sender_fields(
    sender: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    if sender is None:
        return None, None, None

    nickname_raw = sender.get("nickname")
    card_raw = sender.get("card")
    role_raw = sender.get("role")
    nickname = nickname_raw if isinstance(nickname_raw, str) else None
    card = card_raw if isinstance(card_raw, str) else None
    role = role_raw if isinstance(role_raw, str) else None
    return nickname, card, role


async def insert_event(
    *,
    post_type: str,
    message_type: str | None,
    user_id: int | None,
    group_id: int | None,
    group_name: str | None,
    self_id: int | None,
    message_id: str | None,
    event_time: datetime | None,
    raw_message: str | None,
    raw: dict[str, Any],
) -> int:
    payload_hash = hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO onebot_events
            (post_type, message_type, user_id, group_id, group_name, self_id,
             message_id, event_time, raw_message, payload_hash, raw)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
        RETURNING id
        """,
        post_type,
        message_type,
        user_id,
        group_id,
        group_name,
        self_id,
        message_id,
        event_time,
        raw_message,
        payload_hash,
        json.dumps(raw, ensure_ascii=False),
    )
    return row["id"]


async def insert_message(
    *,
    event_id: int,
    message_type: str,
    user_id: int,
    group_id: int | None,
    group_name: str | None,
    sender_nickname: str | None,
    sender_card: str | None,
    sender_role: str | None,
    message_id: str | None,
    plain_text: str | None,
    message_segments: list[dict[str, Any]] | None,
    event_time: datetime,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO onebot_messages
            (event_id, message_type, user_id, group_id, group_name,
             sender_nickname, sender_card, sender_role, message_id,
             plain_text, message_segments, event_time)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
        RETURNING id
        """,
        event_id,
        message_type,
        user_id,
        group_id,
        group_name,
        sender_nickname,
        sender_card,
        sender_role,
        message_id,
        plain_text,
        (
            json.dumps(message_segments, ensure_ascii=False)
            if message_segments is not None
            else None
        ),
        event_time,
    )
    return row["id"]


async def insert_image(
    *,
    event_id: int,
    seq: int,
    url_raw: str | None,
    url_decoded: str | None,
    file_name: str | None,
    sub_type: str | None,
    file_size: int | None,
    summary: str | None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO onebot_message_images
            (event_id, seq, url_raw, url_decoded, file_name, sub_type, file_size, summary)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        RETURNING id
        """,
        event_id,
        seq,
        url_raw,
        url_decoded,
        file_name,
        sub_type,
        file_size,
        summary,
    )
    return row["id"]


async def update_image_refresh_trace(
    image_id: int,
    *,
    refresh_attempt_count: int,
    refresh_trace: dict[str, Any],
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        UPDATE onebot_message_images SET
            refresh_attempt_count=$2,
            refresh_trace=$3::jsonb
        WHERE id=$1
        """,
        image_id,
        max(0, refresh_attempt_count),
        json.dumps(refresh_trace, ensure_ascii=False),
    )


async def update_image_download_success(
    image_id: int,
    *,
    local_path: str,
    hash_sha256: str,
    format: str | None,
    width: int | None,
    height: int | None,
    is_animated: bool | None,
    frame_count: int | None,
    http_content_type: str | None,
    http_content_length: int | None,
    download_attempt: int,
    transfer_mode: str = "normal",
    stream_phase: str | None = None,
    stream_data_type: str | None = None,
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        UPDATE onebot_message_images SET
            download_status='saved',
            local_path=$2,
            downloaded_at=now(),
            hash_sha256=$3,
            format=$4,
            width=$5,
            height=$6,
            is_animated=$7,
            frame_count=$8,
            http_content_type=$9,
            http_content_length=$10,
            download_attempt=$11,
            transfer_mode=$12,
            stream_phase=$13,
            stream_data_type=$14
        WHERE id=$1
        """,
        image_id,
        local_path,
        hash_sha256,
        format,
        width,
        height,
        is_animated,
        frame_count,
        http_content_type,
        http_content_length,
        download_attempt,
        transfer_mode,
        stream_phase,
        stream_data_type,
    )


async def update_image_download_duplicate(
    image_id: int,
    *,
    hash_sha256: str,
    download_attempt: int,
    transfer_mode: str = "normal",
    stream_phase: str | None = None,
    stream_data_type: str | None = None,
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        UPDATE onebot_message_images SET
            download_status='duplicate',
            hash_sha256=$2,
            download_attempt=$3,
            downloaded_at=now(),
            transfer_mode=$4,
            stream_phase=$5,
            stream_data_type=$6
        WHERE id=$1
        """,
        image_id,
        hash_sha256,
        download_attempt,
        transfer_mode,
        stream_phase,
        stream_data_type,
    )


async def update_image_download_failure(
    image_id: int,
    *,
    error: str,
    download_attempt: int,
    stream_phase: str | None = None,
    transfer_mode: str = "normal",
    stream_data_type: str | None = None,
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        UPDATE onebot_message_images SET
            download_status='failed',
            download_error=$2,
            download_attempt=$3,
            stream_phase=$4,
            transfer_mode=$5,
            stream_data_type=$6
        WHERE id=$1
        """,
        image_id,
        error,
        download_attempt,
        stream_phase,
        transfer_mode,
        stream_data_type,
    )


async def insert_nats_dispatch(
    *,
    image_id: int,
    subject: str,
    payload: dict[str, Any],
    status: str,
    error: str | None = None,
) -> int:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO onebot_nats_dispatches (image_id, subject, payload, status, error)
        VALUES ($1,$2,$3::jsonb,$4,$5)
        RETURNING id
        """,
        image_id,
        subject,
        json.dumps(payload, ensure_ascii=False),
        status,
        error,
    )
    return row["id"]
