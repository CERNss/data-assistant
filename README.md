# data-assistant

`data-assistant` is a two-service pipeline:

- `data-logger`: receives NapCat OneBot11 events through reverse WebSocket, persists all events/images to PostgreSQL, and publishes image tagging tasks to NATS.
- `data-processor`: consumes NATS tasks and runs Eagle_AItagger_byWD1.4.

## Services

- Logger entrypoint: `python napcat_logger_service.py`
- Processor entrypoint: `python data_processor_service.py`

## Local Setup

1. Create virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
python -m pip install -U pip
python -m pip install -r requirements.txt
```

3. Prepare environment:

```bash
cp .env.example .env
```

## NapCat Reverse WebSocket

`data-logger` is the fixed server endpoint; NapCat connects to it as client.

- Default endpoint: `ws://<logger-host>:3001/onebot/v11/ws`
- Optional auth header: `Authorization: Bearer <NAPCAT_TOKEN>`

Required logger env vars:

```env
NAPCAT_WS_HOST=0.0.0.0
NAPCAT_WS_PORT=3001
NAPCAT_WS_PATH=/onebot/v11/ws
NAPCAT_TOKEN=
NAPCAT_ACTION_TIMEOUT_SEC=8.0
NAPCAT_RECONNECT_SEC=5.0
NAPCAT_HEARTBEAT_TIMEOUT_SEC=60.0
NAPCAT_BOT_QQ=0
POSTGRES_DSN=postgresql://admin:password@db:5432/app_db
```

## Run Services Locally

Start processor first:

```bash
python data_processor_service.py
```

Then start logger:

```bash
python napcat_logger_service.py
```

## Docker Compose Topology

Compose includes 5 services:

- `nats`
- `db` (PostgreSQL)
- `pgadmin`
- `processor`
- `logger`

Start in recommended order:

```bash
docker compose up -d nats db processor
docker compose up -d logger
```

View logs:

```bash
docker compose logs -f logger processor nats db pgadmin
```

Stop:

```bash
docker compose down
```

## Database Persistence

Logger persists to PostgreSQL:

- `onebot_events`: all inbound OneBot events (`message`, `message_sent`, `notice`, `request`, `meta_event`)
- `onebot_message_images`: one row per extracted image segment, download state, metadata, dedup evidence, refresh trace, transfer state
- `onebot_nats_dispatches`: NATS publish status (`published` / `failed` / `fallback_local`)

## Image Handling

- Primary URL source: `message[].data.url`
- CQ fallback: parse `raw_message` (`[CQ:image,...,url=...]`)
- URL-expiry handling: refresh chain `nc_get_rkey -> get_image -> get_file -> get_msg`
- Metadata: SHA256, format, width/height, animated/frame_count, HTTP content-type/content-length
- Dedup: hash-based duplicate detection with `duplicate` status

## Tagger Integration

Required env vars:

```env
CHAT_IMAGE_TAGGER_ENABLED=true
CHAT_IMAGE_TAGGER_TOOL_ROOT=/absolute/path/to/Eagle_AItagger_byWD1.4
```

NATS env vars:

```env
CHAT_IMAGE_NATS_ENABLED=true
CHAT_IMAGE_NATS_SERVERS=nats://nats:4222
CHAT_IMAGE_NATS_SUBJECT=chat.image.tagger.task
CHAT_IMAGE_NATS_QUEUE_GROUP=chat-image-tagger-workers
CHAT_IMAGE_NATS_CLIENT_NAME=data-assistant
CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC=5
CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC=3
CHAT_IMAGE_NATS_FALLBACK_LOCAL_QUEUE=true
```

## Tests

Run unit tests:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Syntax/import validation:

```bash
python -m compileall .
```

## Observability

- Enable OTel: `OTEL_ENABLED=true`
- Configure endpoint: `OTEL_EXPORTER_OTLP_ENDPOINT=http://<collector>:4317`
- Service identity: `OTEL_SERVICE_NAME`
