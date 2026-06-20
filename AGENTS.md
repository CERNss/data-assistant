# Agents Guide (data-assistant)

This repo is a two-service pipeline that ingests QQ chat events via NapCat OneBot11 reverse WebSocket,
persists events and images to PostgreSQL, and dispatches image tagging tasks to an external AI tagger
(Eagle_AItagger_byWD1.4) through NATS messaging.

## System Architecture

### System Topology

```mermaid
graph TB
    subgraph External
        NapCat["NapCat<br/>(QQ Bot Client)"]
        Tagger["Eagle_AItagger_byWD1.4<br/>(AI Tagger Tool)"]
        OTLP["OTLP Endpoint<br/>(Traces + Metrics + Logs)"]
    end

    subgraph Docker Compose
        subgraph logger["Logger Service (:3001)"]
            WS["WebSocket Server"]
            Handler["Event Handler"]
            Pipeline["Persist Pipeline"]
            Downloader["Image Downloader"]
            NATSPub["NATS Publisher"]
        end

        subgraph processor["Processor Service (:8080)"]
            Worker["Tagger Worker"]
            Queue["Local JSON Queue"]
            TaggerPipeline["Tagger Pipeline"]
        end

        NATS["NATS (:4222)"]
        PG["PostgreSQL (:5432)"]
        FB["Fluent Bit (:24224)"]
        SharedVol[("chat-data volume<br/>/app/data")]
    end

    NapCat -- "reverse WS" --> WS
    WS --> Handler
    Handler --> Pipeline
    Pipeline --> PG
    Pipeline --> Downloader
    Downloader --> SharedVol
    Pipeline --> NATSPub
    NATSPub --> NATS
    NATS --> Worker
    Worker --> Queue
    Queue --> TaggerPipeline
    TaggerPipeline -- "subprocess" --> Tagger
    TaggerPipeline --> SharedVol
    Tagger -. "reads images from" .-> SharedVol
    Tagger -. "writes metadata.json" .-> TaggerPipeline

    logger -- "stdout JSON" --> FB
    processor -- "stdout JSON" --> FB
    FB --> OTLP
    logger -- "OTLP gRPC" --> OTLP
    processor -- "OTLP gRPC" --> OTLP
```

### Data Flow

```mermaid
sequenceDiagram
    participant NC as NapCat (QQ)
    participant LS as Logger Service
    participant PG as PostgreSQL
    participant FS as Shared Volume
    participant NATS as NATS
    participant PS as Processor Service
    participant ET as Eagle AI Tagger

    NC->>LS: WebSocket event (message with image)
    LS->>PG: INSERT onebot_events
    LS->>PG: INSERT onebot_message_images (pending)
    LS->>LS: Download image (retry + URL refresh)
    LS->>FS: Save image file
    LS->>PG: UPDATE image (saved, sha256, metadata)
    LS->>NATS: Publish TaskV2 (image_id, sha256, urls, context)
    LS->>PG: INSERT onebot_nats_dispatches

    NATS->>PS: Deliver message
    PS->>FS: Resolve image path (glob + sha256)
    PS->>PS: Enqueue to local JSON queue
    PS->>PS: Pick batch from queue
    PS->>FS: Stage images (hard-link/copy)
    PS->>ET: subprocess: python main.py --image_list ...
    ET->>FS: Write metadata.json per image
    PS->>PS: Read metadata.json → extract tags
    PS->>FS: Write audit log (group_image_tags.jsonl)
```

### Logger Service

Entry point: `python3 -m logger_service.service.main`

Receives all NapCat OneBot11 events, persists them to PostgreSQL, downloads chat images to shared storage, and publishes tagging tasks to NATS.

```mermaid
flowchart TD
    A["NapCat WebSocket Connection"] --> B["connection.py<br/>aiohttp WS Server"]
    B --> C{"JSON parse + route"}
    C -- "action response<br/>(echo match)" --> D["OneBotActionClient<br/>future resolution"]
    C -- "event push" --> E["handler.py<br/>parse_event()"]
    E --> F["pipeline.py<br/>persist_event()"]

    F --> G["insert_event()<br/>→ onebot_events"]
    G --> H{"post_type == message<br/>or message_sent?"}
    H -- "No" --> Z["Done"]
    H -- "Yes + has images" --> I["For each ImageSegment"]

    I --> J["insert_image()<br/>→ onebot_message_images"]
    J --> K["download_image_with_retry()"]
    K --> L{"Download OK?"}
    L -- "Yes" --> P["SHA256 hash"]
    L -- "URL expired" --> M["refresh_image_url()"]
    M --> N{"Refreshed URL?"}
    N -- "Yes" --> O["Retry download"]
    N -- "No" --> FAIL["mark failed"]
    O --> P

    P --> Q{"Duplicate hash<br/>in DB?"}
    Q -- "Yes" --> DUP["mark duplicate"]
    Q -- "No" --> R["Save to disk"]
    R --> S["update_image_download_success()"]
    S --> T["append audit JSONL"]
    T --> U["build_tagger_task_payload()"]
    U --> V["publish to NATS"]
    V --> W["insert_nats_dispatch()"]
```

URL refresh chain (when image URL expires): `nc_get_rkey → get_image → get_file → get_msg`. Each action is attempted in order via the NapCat action channel. Stops at the first action that returns a valid HTTP URL.

### Processor Service

Entry point: `python3 -m processor_service.service.main`

Subscribes to NATS tagging tasks, resolves image file paths on shared storage, queues them locally, and runs the external tagger in batches via subprocess.

```mermaid
flowchart TD
    A["NATS Subscription<br/>chat.image.tagger.task"] --> B["handle_nats_message()"]
    B --> C["decode_task() → TaskV2"]
    C --> D["_resolve_task_image_path()"]

    D --> D1{"task.image_path exists?"}
    D1 -- "Yes" --> D5["Use direct path"]
    D1 -- "No" --> D2{"context.image_path?"}
    D2 -- "Yes" --> D5
    D2 -- "No" --> D3["Glob: *_{message_id}_{seq}_*"]
    D3 --> D4{"SHA256 match?"}
    D4 -- "Yes" --> D5
    D4 -- "No" --> D5b["Use newest candidate"]

    D5 --> E["enqueue_tagger_task_payload()"]
    D5b --> E
    E --> F["Local JSON Queue<br/>(atomic write)"]
    F --> G["run_tagger_once()"]

    G --> H["Pick batch_size items"]
    H --> I["_run_external_tagger_batch()"]

    I --> I1["Create run_dir + stage/"]
    I1 --> I2["Hard-link or copy images"]
    I2 --> I3["Generate image_list.txt"]
    I3 --> I4["subprocess.run()<br/>python main.py --image_list ... --config ..."]
    I4 --> I5["Read metadata.json per image"]

    I5 --> J{"Result?"}
    J -- "success" --> K["Audit log: tags"]
    J -- "failed + retries left" --> L["Requeue"]
    J -- "failed + max attempts" --> M["Audit log: failed"]
```

### Shared Contract

Services communicate via NATS using `contracts/chat_image_task.py`:

```
TaskV2 {
    version: int           # Protocol version (currently 2)
    image_id: int          # DB primary key from onebot_message_images
    sha256: str            # SHA256 hash of downloaded image
    source_url: str        # URL used for successful download
    original_url: str      # Original URL from OneBot event
    context: dict          # event_id, chat_type, chat_id, message_id, seq, etc.
    image_path: str | None # Optional explicit file path (not set in normal flow)
}
```

V1 payloads (legacy `{image_path, context}` without `version` field) are transparently decoded into TaskV2.

### External Tool Contract

Eagle_AItagger_byWD1.4 is invoked as a CLI subprocess. It is **not included** in this repository and must be manually installed on the host.

- **Input**: `--image_list <path>` text file, one image absolute path per line.
- **Output**: `metadata.json` written alongside each input image: `{"tags": [...]}`
- **Mount**: Host directory bind-mounted read-only into processor container at `/opt/tagger`.

### Database Schema

```mermaid
erDiagram
    onebot_events {
        bigserial id PK
        timestamptz received_at
        text post_type
        text message_type
        bigint user_id
        bigint group_id
        text group_name
        bigint self_id
        text message_id
        timestamptz event_time
        text raw_message
        text payload_hash
        jsonb raw
    }

    onebot_messages {
        bigserial id PK
        bigint event_id FK
        text message_type
        bigint user_id
        bigint group_id
        text group_name
        text sender_nickname
        text sender_card
        text sender_role
        text message_id
        text plain_text
        jsonb message_segments
        timestamptz event_time
    }

    onebot_message_images {
        bigserial id PK
        bigint event_id FK
        int seq
        text url_raw
        text url_decoded
        text file_name
        text sub_type
        bigint file_size
        text summary
        text local_path
        text download_status
        text download_error
        timestamptz downloaded_at
        text hash_sha256
        text format
        int width
        int height
        boolean is_animated
        int frame_count
        text http_content_type
        bigint http_content_length
        int download_attempt
        int refresh_attempt_count
        jsonb refresh_trace
        text transfer_mode
        text stream_phase
        text stream_data_type
    }

    onebot_nats_dispatches {
        bigserial id PK
        bigint image_id FK
        text subject
        jsonb payload
        text status
        text error
    }

    onebot_events ||--o{ onebot_messages : "event_id"
    onebot_events ||--o{ onebot_message_images : "event_id"
    onebot_message_images ||--o{ onebot_nats_dispatches : "image_id"
```

Image status lifecycle: `pending → saved | duplicate | failed`

### Observability

```mermaid
flowchart LR
    subgraph Services
        LS["Logger Service"]
        PS["Processor Service"]
    end

    subgraph Log Pipeline
        LS -- "stdout JSON" --> Docker["Docker fluentd driver"]
        PS -- "stdout JSON" --> Docker
        Docker --> FB["Fluent Bit (:24224)"]
        FB -- "OTLP HTTP" --> Collector["OTLP Endpoint"]
    end

    subgraph Trace + Metrics Pipeline
        LS -- "OTLP gRPC" --> Collector
        PS -- "OTLP gRPC" --> Collector
    end
```

Key metrics:

| Service | Metric | Type | Description |
|---------|--------|------|-------------|
| Logger | `logger_events_total` | Counter | Events by persist outcome + post_type |
| Logger | `logger_images_total` | Counter | Image processing outcomes |
| Logger | `logger_image_process_duration_ms` | Histogram | Image processing latency |
| Logger | `logger_nats_publish_total` | Counter | NATS publish attempts by outcome |
| Logger | `logger_nats_publish_latency_ms` | Histogram | NATS publish latency |
| Processor | `processor_nats_messages_total` | Counter | NATS messages handled by outcome |
| Processor | `processor_nats_message_handle_latency_ms` | Histogram | Message handling latency |
| Processor | `processor_queue_enqueued_total` | Counter | Queue enqueue by outcome |
| Processor | `processor_queue_depth` | Histogram | Queue depth samples |
| Processor | `processor_tagger_batches_total` | Counter | Tagger batch outcomes |
| Processor | `processor_tagger_items_total` | Counter | Tagger item outcomes |
| Processor | `processor_tagger_batch_latency_ms` | Histogram | Tagger batch latency |

### Filesystem Layout (Runtime)

```
/app/data/                              # Shared Docker volume (chat-data)
├── chat_images/                        # Image storage root
│   ├── group/<group_id>/               # Group chat images
│   │   └── <timestamp>_<msg_id>_<seq>_<filename>
│   └── private/<user_id>/              # Private chat images
│       └── <timestamp>_<msg_id>_<seq>_<filename>
├── chat_image_tagger_queue.json        # Processor local task queue
├── chat_image_tagger_runs/             # Tagger staging (ephemeral)
│   └── <run_id>/
│       ├── image_list.txt
│       └── stage/00000.info/
│           ├── <image_file>            # Hard-linked from chat_images/
│           └── metadata.json           # Written by tagger
├── group_image_tags.jsonl              # Tagger audit log (tag results)
└── group_images.jsonl                  # Logger image audit log
```

### Network Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Logger | 3001 | WS | NapCat reverse WebSocket + `/health` |
| Processor | 8080 | HTTP | `/health` endpoint |
| NATS | 4222 | TCP | Client connections |
| NATS | 8222 | HTTP | Monitoring |
| PostgreSQL | 5432 (→25432) | TCP | Database |
| pgAdmin | 80 (→25050) | HTTP | DB admin UI |
| Fluent Bit | 24224 | TCP/UDP | Log forwarding (fluentd protocol) |

### Known Limitations

1. **Tags not persisted to DB** — Tagger results only go to `group_image_tags.jsonl`; no structured query capability for tags.
2. **Legacy core NATS mode is best-effort** — JetStream is enabled by default; if `CHAT_IMAGE_NATS_JETSTREAM_ENABLED=false`, messages can still be lost when no subscriber is active.
3. **No tag-based classification** — Images stay in their original directory; no post-tagging reorganization.
4. **External tagger dependency** — Eagle_AItagger_byWD1.4 must be manually installed; not pulled or managed by this project.
5. **Single audit log file** — `group_image_tags.jsonl` grows unbounded with no rotation.

## Commands

### Setup (local dev)

- Create venv (recommended):
  - `python -m venv .venv`
  - `source .venv/bin/activate`
- Install runtime deps:
  - `python -m pip install -U pip`
  - `python -m pip install -r requirements.txt`

Python requirement: `>=3.10` (Dockerfiles use `python:3.11-slim`).

### Run (local)

- Logger service (NapCat reverse WS server):
  - `python3 -m logger_service.service.main`
- Processor service (tagger worker):
  - `python3 -m processor_service.service.main`
  - or `python3 -m processor_service.service.chat_image.tagger_worker`
- Manual local tagging (no NATS):
  - `python3 -m processor_service.service.chat_image.tagger_cli`
  - one batch: `python3 -m processor_service.service.chat_image.tagger_cli --once`

### Docker Compose (logger + processor + NATS)

- Prepare env:
  - `cp .env.example .env`
  - set `CHAT_IMAGE_TAGGER_TOOL_ROOT_HOST` in `.env` (host path to Eagle_AItagger_byWD1.4)
- Start (recommended order):
  - `docker compose up -d nats fluent-bit processor`
  - `docker compose up -d logger`
- Logs: `docker compose logs -f logger processor fluent-bit nats`
- Stop: `docker compose down`

### Tests

Tests are `unittest`-based (including async via `unittest.IsolatedAsyncioTestCase`).

- Run all tests:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`

- Run a single test module:
  - `python3 -m unittest tests.test_chat_image_storage`

- Run a single test class:
  - `python3 -m unittest tests.test_chat_image_tagger_worker.TestChatImageTaggerWorker`

- Run a single test method:
  - `python3 -m unittest tests.test_chat_image_tagger_pipeline.TestChatImageTaggerPipeline.test_run_once_success`

### Lint / Format

There is no repo-pinned linter/formatter config (no `ruff.toml`, `pyproject` tool config, etc.).

- Minimal sanity check:
  - `python3 -m compileall .`

- Optional (if you install ruff locally):
  - `python -m pip install ruff`
  - `ruff check .`
  - `ruff format .`

## Code Style (follow existing patterns)

### Imports

- If a module uses postponed annotations, keep `from __future__ import annotations` as the first import.
- Group imports: stdlib, third-party, then local.
- Prefer package-relative imports inside service packages (e.g. `from .audit import ...`).
- Tests typically import via the repo root package path (e.g. `from logger_service.service...` or `from processor_service.service...`).

### Formatting

- Use 4-space indentation; keep formatting Black-compatible (trailing commas in multi-line literals).
- Prefer f-strings for string composition; keep log messages parameterized (see Logging).
- Use `Path` over raw strings for filesystem paths.

### Types

- Use modern annotations: `list[T]`, `dict[str, Any]`, `X | None`.
- Add return types on public functions and tests (`-> None`), as the codebase does.
- Use `Any` sparingly; validate untyped inputs at boundaries (e.g. decoded JSON, NATS messages).

### Naming

- Functions/vars: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE_CASE`.
- Keep env var names stable and documented; config parsing lives in service-scoped modules under `logger_service/service/chat_image/` and `processor_service/service/chat_image/`.
- Tracer names follow dotted paths like `data_assistant.<service>.<module>`.

### Logging and Tracing

- Use Loguru-style `{}` formatting in service code:
  - `logger.info("Saved chat image: path={} size={}", path, size)`
- Logger/processor runtime logs are emitted as JSON to stdout and forwarded by Fluent Bit.
- Traces and metrics are exported via in-process OpenTelemetry SDK OTLP exporters.
- Wrap meaningful operations with OpenTelemetry spans when appropriate (pattern in `logger_service/service/napcat/pipeline.py`).

### Error Handling

- Prefer specific exceptions (`ValueError` for invalid payloads, `RuntimeError` for misconfiguration).
- Catch broad `Exception` only at system boundaries (event handlers, message processing, subprocess calls).
- When re-raising, use exception chaining: `raise RuntimeError("...") from exc`.
- On recoverable failures, log and continue; avoid crashing long-running services.

### I/O and Data Files

- Runtime output goes under `data/` (gitignored). Do not commit generated `.jsonl` logs or queues.
- JSON output uses UTF-8 and `ensure_ascii=False` (see `logger_service/service/chat_image/audit.py`).
- When persisting structured state, prefer atomic writes (write tmp + replace) as done for tagger queue.

### Async / Concurrency

- Keep QQ handlers non-blocking; do network I/O with `aiohttp` and use retries (`downloader.py`).
- Protect shared on-disk queue state with `asyncio.Lock` (`tagger_pipeline.py`).
- Offload blocking work (subprocess, heavy I/O) via `asyncio.to_thread`.

### Tests

- Use `unittest` (not pytest) unless the repo explicitly adopts it.
- Prefer hermetic tests: use `tempfile.TemporaryDirectory()` and avoid touching `data/`.
- For async tests, inherit from `unittest.IsolatedAsyncioTestCase`.

## Repo-Specific Gotchas

- `docker-compose.yml` mounts a shared `/app/data` volume for logger + processor; paths must match.
- Fluent Bit config files live at `fluent-bit/fluent-bit.conf` and `fluent-bit/parsers.conf`; compose mounts both read-only.
- Docker build context ignores `tests/` and `openspec/` (`.dockerignore`), so containers cannot run tests.
- Secrets live in `.env`; never commit real QQ credentials or tokens.
- NATS publishing uses JetStream by default; only legacy core pub/sub mode is best-effort.

## Agent Workflow Notes

This repo includes an OpenSpec-based workflow under `openspec/` with helper prompts in:
- `.opencode/command/` (opsx commands)
- `.opencode/skills/` (skill instructions)
- `.claude/commands/` and `.claude/skills/` (similar content for other agents)

If a task references an “OpenSpec change”, look under `openspec/changes/<change-name>/`.
