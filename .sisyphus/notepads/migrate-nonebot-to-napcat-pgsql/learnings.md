# Learnings

## [2026-03-10] Orchestrator: Initial codebase analysis

### Existing patterns to follow
- Config: frozen dataclass + `load_*_config()` factory, `_env_bool/_env_int/_env_float` helpers (see `plugins/chat_image/config.py`)
- Imports: `from __future__ import annotations` first; stdlib → third-party → local; package-relative inside `plugins/`
- Logging: use `from loguru import logger` (NOT `from nonebot import logger`) in all new/migrated files
- OTel: `trace.get_tracer("data_assistant.plugins.<module>.<file>")` pattern
- Error handling: specific exceptions at boundaries; `raise X from exc` chaining; catch broad `Exception` only at system boundaries
- Async: `asyncio.Lock` for shared state; `asyncio.to_thread` for blocking I/O; `aiohttp` for HTTP
- Path: always use `Path` over raw strings
- JSON: `ensure_ascii=False`, UTF-8

### Files using `from nonebot import logger` that MUST be migrated
- `plugins/chat_image/nats_task_bus.py`
- `plugins/chat_image/tagger_pipeline.py`
- `plugins/chat_image/tagger_worker.py`
- `plugins/chat_image/service.py`

### Key existing modules (keep unchanged unless noted)
- `plugins/chat_image/downloader.py` — `download_image_bytes_with_retry(url, config)` returns `(bytes, int)`
- `plugins/chat_image/storage.py` — `build_image_save_path(...)`, `is_image_attachment(...)`
- `plugins/chat_image/audit.py` — `append_json_line(path, dict)`
- `plugins/chat_image/nats_task_bus.py` — `publish_tagger_task(config, image_path, context)` returns bool
- `plugins/chat_image/tagger_pipeline.py` — `enqueue_image_for_tagging`, `enqueue_tagger_task_payload`
- `telemetry.py` — `init_telemetry()`, `install_error_hooks()` — keep unchanged

### NapCat event facts
- All events: `time` (seconds), `self_id`, `post_type`
- `post_type` values: `message`, `message_sent`, `notice`, `request`, `meta_event`
- `message` field: array of segments OR CQ string — must handle both
- `message_format=array` → prefer `message[].data.url` for images
- `raw_message` CQ fallback: may have HTML-encoded `&amp;` — decode before use
- `heartbeat.interval` is milliseconds (not seconds)
- Image URL expiry ~2 hours; refresh via `nc_get_rkey`/`get_image`/`get_file`/`get_msg`

### PostgreSQL schema (3 tables)
- `onebot_events`: raw JSONB + indexed columns
- `onebot_message_images`: one row per image segment, download + metadata
- `onebot_nats_dispatches`: NATS publish status per image

### Write order (critical)
1. Write `onebot_events` first
2. Download image → write `onebot_message_images`
3. Publish NATS → write `onebot_nats_dispatches`

## [2026-03-10] Task: Wave 1B persistence plugin

### plugins/persistence/ package created
- 4 files: `__init__.py`, `config.py`, `db.py`, `repository.py`
- `python3 -m compileall plugins/persistence/` exits 0

### asyncpg specifics confirmed
- Positional params: `$1,$2,...` (NOT `%s` or `:name`)
- jsonb: must pass `json.dumps(...)` string, NOT Python dict — cast with `$N::jsonb`
- Pool created with `asyncpg.create_pool(dsn, min_size=2, max_size=10)`
- Pool methods: `.acquire()` (async context manager), `.execute()`, `.fetchrow()`
- `fetchrow()` returns record dict; access by column name: `row["id"]`

### LSP note
- `asyncpg` LSP errors expected until Wave 3 adds it to `requirements.txt`
- Pre-existing `telemetry.py` LSP errors unrelated to this package

### Config pattern reuse
- Copied `_env_bool/_env_int/_env_float` helpers verbatim from `plugins/chat_image/config.py`
- `PostgresConfig` is a frozen dataclass with single field `dsn: str`
- `load_postgres_config()` reads `POSTGRES_DSN` env var, defaults to `postgresql://admin:password@localhost:5432/app_db`

### DDL idempotency
- All `CREATE TABLE` and `CREATE INDEX` use `IF NOT EXISTS`
- Schema covers tasks 2.1–2.8: events, images (with binary metadata + dedup + stream fields), NATS dispatches

### Download status values
- `pending` (default at insert), `saved` (success), `duplicate` (hash collision), `failed` (error)

## [2026-03-10] Task: Wave 1A napcat plugin

### Files created
- `plugins/napcat/__init__.py` — exports 7 public symbols
- `plugins/napcat/config.py` — `NapCatConfig` frozen dataclass + `load_napcat_config()` + copied `_env_bool/_env_int/_env_float` helpers
- `plugins/napcat/connection.py` — aiohttp WS reverse server; token auth via `Authorization: Bearer`; lifecycle logging
- `plugins/napcat/event.py` — `OneBotEvent` + `ImageSegment` dataclasses; `parse_event()` raises `ValueError` on missing envelope fields
- `plugins/napcat/handler.py` — `handle_raw_event()` + `refresh_image_url()` stub

### Patterns applied
- `_env_int` minimum=0 for bot_qq/ws_port to allow 0 and low port numbers (vs chat_image which uses minimum=1)
- `_env_int` for ws_port uses minimum=1 so port stays ≥1
- Image URL extraction: segments → CQ fallback chain; both `url_raw` and `url_decoded` preserved
- `sub_type` from image segments cast to `str` (protocol sends int 0/1, but keep as str for uniformity)
- `refresh_image_url` is a stub; call chain documented: nc_get_rkey → get_image → get_file → get_msg
- `connection.py` imports `asyncio` lazily inside `_block_forever` to avoid module-level circular issues

### Gotchas
- The venv at `.venv/` has a broken interpreter path (points to old data-logger path). Use system python3 with pip3-installed aiohttp/loguru for import verification.
- `python3 -m compileall plugins/napcat/` only shows `__init__.py` without `-r` flag and still only recurses one level; list files explicitly for reliable verification.
- Edit tool replaces first match; when oldString occurs multiple times (e.g. duplicate content from Write→Edit sequence), must make oldString unique by including surrounding context.

## [2026-03-10] Task: Wave 3 pipeline integration (tasks 3.1–3.3)

### Files created
- `plugins/napcat/pipeline.py` — `persist_event(event)` + `_process_image(...)` helpers
- `napcat_logger_service.py` — new entry point wiring WS server → handler → pipeline → DB

### Files modified
- `plugins/napcat/__init__.py` — added `from .pipeline import persist_event` + added to `__all__`

### Pipeline write order (confirmed)
1. `insert_event` → get `event_id`
2. For each image: `insert_image` (pending) → download → hash → dedup check → write file → `update_image_download_success` / `update_image_download_duplicate` / `update_image_download_failure`
3. `insert_nats_dispatch` (published / failed / fallback_local)

### Dedup check pattern
- Raw DB query (no repository function): `SELECT id FROM onebot_message_images WHERE hash_sha256=$1 AND download_status='saved' LIMIT 1`
- Uses `get_pool()` directly from `plugins.persistence.db`
- If duplicate: mark as `duplicate`, return (skip NATS dispatch for that image)

### Lazy imports pattern (used in pipeline.py)
- All `plugins.chat_image.*` and `plugins.persistence.*` imports are deferred inside function bodies
- Rationale: avoid potential circular imports at module load time
- `PIL.Image` import is inside a try/except — graceful degradation if Pillow not installed (Wave 3 adds it to requirements.txt)

### NATS fallback decision tree
- `nats.enabled=True, publish succeeded` → status `published`
- `nats.enabled=True, publish failed, fallback_to_local_queue=True` → `enqueue_tagger_task_payload` → status `fallback_local`
- `nats.enabled=False` → `enqueue_image_for_tagging` → status `fallback_local`
- Error in fallback → status `failed`, `nats_error` set

### Entry point architecture
- `napcat_logger_service.py` mirrors `data_logger_service.py` structure but uses PostgreSQL + napcat WS
- `data_logger_service.py` is unchanged (NoneBot rollback path preserved)
- DB init/close wraps `run_server` in try/finally — pool always cleaned up

### PIL LSP error
- `Import "PIL" could not be resolved` in pipeline.py — expected, Pillow not yet in requirements.txt
- Handled by `try/except Exception` around PIL usage — graceful degradation to `fmt=None`

### compileall result
- All 3 files pass `python3 -m compileall` with exit 0

## [2026-03-10] Task: Wave 4 tests

### service.py nonebot fix
- Removed `from nonebot.adapters import Bot` (line 7 of service.py); replaced `bot: Bot` with `bot: Any`
- `Any` was already imported from `typing` — no new import needed

### asyncpg stub pattern for persistence tests
- `plugins/persistence/__init__.py` re-exports from `db.py` which does `import asyncpg` at module level
- Importing any symbol from `plugins.persistence.*` triggers `__init__.py` → `db.py` → `asyncpg`
- Fix: inject a `types.ModuleType("asyncpg")` stub into `sys.modules["asyncpg"]` at the top of the test file BEFORE the `from plugins.persistence...` import
- Must stub `.Pool`, `.Connection`, `.create_pool` attributes to avoid AttributeError in `db.py` type annotations

### Test runner
- Use `.venv/bin/python` not system `python3` (system is 3.14, venv is 3.12 with all deps)
- All 69 tests pass: 12 pre-existing + 27 napcat_event + 10 napcat_config + 5 persistence_config + rest
- compileall exits 0 for plugins/ and napcat_logger_service.py
