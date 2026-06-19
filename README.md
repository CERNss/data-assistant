# data-assistant

`data-assistant` is a two-service pipeline:

- `logger_service`: receives NapCat OneBot11 events through reverse WebSocket, persists all events/images to PostgreSQL, and publishes image tagging tasks to NATS.
- `processor_service`: consumes NATS tasks and calls Eagle_AItagger_byWD1.4 over HTTP.

## Services

- Logger entrypoint: `python3 -m logger_service.service.main`
- Processor entrypoint: `python3 -m processor_service.service.main`
- Service folders:
  - `logger_service/service/`
  - `processor_service/service/`
- Shared contract package:
  - `contracts/chat_image_task.py`

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
./init.sh --tagger-base-url http://host.docker.internal:8000
```

This will:

- create runtime directories under `./.data/`
- initialize queue/log files used by the processor/logger
- copy `.env.example` to `.env` if needed
- pull logger/processor images from Docker Hub and retag them locally for compose
- set `CHAT_IMAGE_TAGGER_BASE_URL` in `.env` when you pass `--tagger-base-url`

## NapCat Reverse WebSocket

`logger_service` is the fixed server endpoint; NapCat connects to it as client.

- Default endpoint: `ws://<logger-host>:8082/onebot/v11/ws`
- Optional auth header: `Authorization: Bearer <NAPCAT_TOKEN>`

Required logger env vars:

```env
NAPCAT_WS_HOST=0.0.0.0
NAPCAT_WS_PORT=8082
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
python3 -m processor_service.service.main
```

Then start logger:

```bash
python3 -m logger_service.service.main
```

## Docker Compose Topology

Compose includes 6 services:

- `nats`
- `db` (PostgreSQL)
- `pgadmin`
- `fluent-bit`
- `processor`
- `logger`

Start in recommended order:

```bash
docker compose up -d nats db fluent-bit processor
docker compose up -d logger
```

View logs:

```bash
docker compose logs -f logger processor fluent-bit nats db pgadmin
```

Stop:

```bash
docker compose down
```

## Python Image Publish Workflow

GitHub Actions publishes the Python service images independently from any Go project:

- `data-assistant-logger`
- `data-assistant-processor`

Configure these GitHub repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Optionally configure these repository variables:

- `DOCKERHUB_NAMESPACE` (defaults to `DOCKERHUB_USERNAME`)
- `DOCKER_PLATFORMS` (defaults to `linux/amd64,linux/arm64`)

Image publishing is tag-driven. Push a Python release tag to build and push both
service images:

```bash
git tag python-v1.0.0
git push origin python-v1.0.0
```

Branch pushes and pull requests run tests only; they do not publish Docker images.
Release tags also publish `latest`.

Build and push service images manually:

```bash
DOCKERHUB_NAMESPACE=<namespace> ./build.sh all
```

On the deployment server:

```bash
./init.sh --dockerhub-namespace <namespace> --tagger-base-url http://host.docker.internal:8000
docker compose up -d
```

## Database Persistence

Logger persists to PostgreSQL:

- `onebot_events`: all inbound OneBot events (`message`, `message_sent`, `notice`, `request`, `meta_event`)
- `onebot_message_images`: one row per extracted image segment, download state, metadata, dedup evidence, refresh trace, transfer state
- `onebot_nats_dispatches`: NATS publish status (`published` / `failed`)

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
CHAT_IMAGE_TAGGER_BASE_URL=http://host.docker.internal:8000
```

Recommended deployment pattern:

- mount the shared host image directory into `logger`, `processor`, and Eagle tagger at the same container path: `/data/images`
- let `logger` save downloaded images to `/data/images`
- let `processor` send those same `/data/images/...` paths to `POST /tag/batch`

NATS env vars:

```env
CHAT_IMAGE_NATS_ENABLED=true
CHAT_IMAGE_NATS_SERVERS=nats://nats:4222
CHAT_IMAGE_NATS_SUBJECT=chat.image.tagger.task
CHAT_IMAGE_NATS_QUEUE_GROUP=chat-image-tagger-workers
CHAT_IMAGE_NATS_CLIENT_NAME=data-assistant
CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC=5
CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC=3
```

## Tests

Run unit tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Syntax/import validation:

```bash
python3 -m compileall logger_service processor_service contracts tests
```

## Observability

- Logs pipeline:
  - `Python logging/loguru -> stdout(JSON) -> Docker fluentd driver -> Fluent Bit -> OTLP logs endpoint`
- Traces pipeline:
  - `Python app -> OpenTelemetry SDK -> OTLP trace endpoint`
- Metrics pipeline:
  - `Python app -> OpenTelemetry SDK -> OTLP metrics endpoint`

Core env vars for logger/processor:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=data-assistant-logger
OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4317
OTEL_EXPORTER_OTLP_INSECURE=true
OTEL_EXPORTER_OTLP_HEADERS=
OTEL_METRIC_EXPORT_INTERVAL_MS=60000
```

Fluent Bit forwarding env vars (compose service):

```env
FB_OTLP_HOST=host.docker.internal
FB_OTLP_PORT=4318
FB_OTLP_LOGS_URI=/v1/logs
FB_OTLP_TLS=Off
FB_OTLP_TLS_VERIFY=Off
```
