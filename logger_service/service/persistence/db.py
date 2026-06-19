from __future__ import annotations

from typing import Any

import asyncpg
from loguru import logger

from .config import PostgresConfig

_pool: asyncpg.Pool | None = None

DDL_SQL = """
CREATE TABLE IF NOT EXISTS onebot_events (
    id bigserial PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now(),
    post_type text NOT NULL,
    message_type text,
    user_id bigint,
    group_id bigint,
    group_name text,
    self_id bigint,
    message_id text,
    event_time timestamptz,
    raw_message text,
    payload_hash text,
    raw jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_onebot_events_post_type ON onebot_events(post_type);
CREATE INDEX IF NOT EXISTS idx_onebot_events_user_id ON onebot_events(user_id);
CREATE INDEX IF NOT EXISTS idx_onebot_events_group_id ON onebot_events(group_id);
CREATE INDEX IF NOT EXISTS idx_onebot_events_received_at ON onebot_events(received_at);
CREATE INDEX IF NOT EXISTS idx_onebot_events_message_id ON onebot_events(message_id);

CREATE TABLE IF NOT EXISTS onebot_messages (
    id bigserial PRIMARY KEY,
    event_id bigint NOT NULL REFERENCES onebot_events(id) ON DELETE CASCADE,
    message_type text NOT NULL,
    user_id bigint NOT NULL,
    group_id bigint,
    group_name text,
    sender_nickname text,
    sender_card text,
    sender_role text,
    message_id text,
    plain_text text,
    message_segments jsonb,
    event_time timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onebot_messages_user_id ON onebot_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_onebot_messages_group_id ON onebot_messages(group_id);
CREATE INDEX IF NOT EXISTS idx_onebot_messages_event_time ON onebot_messages(event_time);

CREATE TABLE IF NOT EXISTS onebot_message_images (
    id bigserial PRIMARY KEY,
    event_id bigint NOT NULL REFERENCES onebot_events(id) ON DELETE CASCADE,
    seq int NOT NULL,
    url_raw text,
    url_decoded text,
    file_name text,
    sub_type text,
    file_size bigint,
    summary text,
    local_path text,
    download_status text NOT NULL DEFAULT 'pending',
    download_error text,
    downloaded_at timestamptz,
    hash_sha256 text,
    format text,
    width int,
    height int,
    is_animated boolean,
    frame_count int,
    http_content_type text,
    http_content_length bigint,
    download_attempt int DEFAULT 0,
    refresh_attempt_count int NOT NULL DEFAULT 0,
    refresh_trace jsonb,
    transfer_mode text,
    stream_phase text,
    stream_data_type text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(event_id, seq)
);

ALTER TABLE onebot_message_images
    ADD COLUMN IF NOT EXISTS refresh_attempt_count int NOT NULL DEFAULT 0;

ALTER TABLE onebot_message_images
    ADD COLUMN IF NOT EXISTS refresh_trace jsonb;

ALTER TABLE onebot_message_images
    ADD COLUMN IF NOT EXISTS stream_data_type text;

CREATE INDEX IF NOT EXISTS idx_onebot_images_event_id ON onebot_message_images(event_id);
CREATE INDEX IF NOT EXISTS idx_onebot_images_hash ON onebot_message_images(hash_sha256);
CREATE INDEX IF NOT EXISTS idx_onebot_images_status ON onebot_message_images(download_status);
CREATE INDEX IF NOT EXISTS idx_onebot_images_transfer_state
    ON onebot_message_images(transfer_mode, stream_phase, stream_data_type);

CREATE TABLE IF NOT EXISTS onebot_nats_dispatches (
    id bigserial PRIMARY KEY,
    image_id bigint NOT NULL REFERENCES onebot_message_images(id) ON DELETE CASCADE,
    subject text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL,
    error text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onebot_nats_image_id ON onebot_nats_dispatches(image_id);
CREATE INDEX IF NOT EXISTS idx_onebot_nats_status ON onebot_nats_dispatches(status);
"""


async def init_db(config: PostgresConfig) -> None:
    global _pool
    _pool = await asyncpg.create_pool(config.dsn, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await _run_ddl(conn)
    logger.info("PostgreSQL pool initialized: dsn={}", config.dsn)


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call init_db() first.")
    return _pool


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed.")


async def _run_ddl(conn: Any) -> None:
    await conn.execute(DDL_SQL)
