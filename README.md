# data-assistant

## How to start

1. generate project using `nb create` .
2. install plugins using `nb plugin install` .
3. run services:
   - collector (`data-logger`): `python data_logger_service.py`
   - processor (`data-processor`): `python data_processor_service.py`

## Documentation

See [Docs](https://nonebot.dev/)

## Group Message Logger

- Entry point: `bot.py`
- Plugin: `plugins/group_logger.py`
- Output files:
  - `data/group_messages.jsonl`: group message events
  - `data/group_notices.jsonl`: group receive/reject notice events

### QQ Adapter Config Example (`.env.prod`)

```env
DRIVER=~fastapi+~aiohttp
HOST=127.0.0.1
PORT=8080
QQ_BOTS=[{"id":"<appid>","token":"<token>","secret":"<secret>"}]
CHAT_IMAGE_SAVE_DIR=data/chat_images
GROUP_IMAGE_TIMEOUT_SEC=20
GROUP_IMAGE_RETRY_COUNT=3
GROUP_IMAGE_RETRY_DELAY_SEC=0.8
OTEL_ENABLED=true
OTEL_SERVICE_NAME=data-assistant-logger
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
OTEL_EXPORTER_OTLP_INSECURE=true
# Optional: key1=value1,key2=value2
OTEL_EXPORTER_OTLP_HEADERS=
```

Note: the bot can only log events pushed by QQ platform after the bot is online and has permissions. It cannot read chat history retroactively.

## Group Image Archiving

- Images are saved by chat identity:
  - Group chat: `<CHAT_IMAGE_SAVE_DIR>/group/<group_openid>/`
  - Private chat: `<CHAT_IMAGE_SAVE_DIR>/private/<user_openid>/`
- Audit log is written to:
  - `data/group_images.jsonl`
- Quality strategy:
  - The bot downloads the attachment URL as-is (no compression/transcoding), preserving the best quality available from QQ attachment URL.
- Retry strategy:
  - On download failure, retry by `GROUP_IMAGE_RETRY_COUNT` with `GROUP_IMAGE_RETRY_DELAY_SEC` seconds delay between attempts.
- Backward compatibility:
  - `GROUP_IMAGE_SAVE_DIR` is still supported as a fallback if `CHAT_IMAGE_SAVE_DIR` is not set.

## Collect Then Tag (Eagle_AItagger_byWD1.4)

- Integration target: [Ir-Phen/Eagle_AItagger_byWD1.4](https://github.com/Ir-Phen/Eagle_AItagger_byWD1.4)
- Pipeline:
  - Step 1: collector service (`bot.py`) collects and stores original images
  - Step 2: collector publishes tagging task to NATS
  - Step 3: tagger worker service subscribes NATS and executes tagging pipeline
- Tagging audit log:
  - `data/group_image_tags.jsonl`

### Required env vars for tagger

```env
CHAT_IMAGE_TAGGER_ENABLED=true
CHAT_IMAGE_TAGGER_TOOL_ROOT=/absolute/path/to/Eagle_AItagger_byWD1.4
```

### NATS env vars

```env
CHAT_IMAGE_NATS_ENABLED=true
CHAT_IMAGE_NATS_SERVERS=nats://127.0.0.1:4222
CHAT_IMAGE_NATS_SUBJECT=chat.image.tagger.task
CHAT_IMAGE_NATS_QUEUE_GROUP=chat-image-tagger-workers
CHAT_IMAGE_NATS_CLIENT_NAME=data-assistant
CHAT_IMAGE_NATS_CONNECT_TIMEOUT_SEC=5
CHAT_IMAGE_NATS_PUBLISH_TIMEOUT_SEC=3
CHAT_IMAGE_NATS_FALLBACK_LOCAL_QUEUE=true
```

### Tagger optional env vars

```env
CHAT_IMAGE_TAGGER_AUTO_RUN=false
CHAT_IMAGE_TAGGER_PYTHON=python
CHAT_IMAGE_TAGGER_ENTRY_SCRIPT=main.py
CHAT_IMAGE_TAGGER_CONFIG=config.ini
CHAT_IMAGE_TAGGER_BATCH_SIZE=16
CHAT_IMAGE_TAGGER_TIMEOUT_SEC=3600
CHAT_IMAGE_TAGGER_MAX_ATTEMPTS=3
CHAT_IMAGE_TAGGER_QUEUE_FILE=data/chat_image_tagger_queue.json
CHAT_IMAGE_TAGGER_RUN_ROOT=data/chat_image_tagger_runs
CHAT_IMAGE_TAGGER_AUDIT_LOG_FILE=data/group_image_tags.jsonl
CHAT_IMAGE_TAGGER_KEEP_RUN_ARTIFACTS=false
```

### Run as two microservices

Start NATS first (example):

```bash
nats-server -js
```

Start processor service (`data-processor`) first:

```bash
python data_processor_service.py
```

Then start collector service (`data-logger`):

```bash
python data_logger_service.py
```

Note: current implementation uses core NATS pub/sub semantics. If no worker is subscribed, published tasks can be lost. For stronger delivery guarantees, use persistent messaging (for example, NATS JetStream durable consumers).

### Run with Docker Compose (logger image + processor image + official NATS image)

Container topology:
- `logger`: built from `Dockerfile.logger`, runs collector only
- `processor`: built from `Dockerfile.processor`, runs worker only
- `nats`: official image `nats:2.10-alpine`

Critical runtime constraints:
- `logger` and `processor` MUST mount the same data volume at the same container path: `/app/data`
- NATS discovery MUST use service name: `nats://nats:4222`
- Startup order SHOULD be: `nats -> processor -> logger`

Prepare environment:

```bash
cp .env.example .env
```

Start NATS + processor first:

```bash
docker compose up -d nats processor
```

Then start logger:

```bash
docker compose up -d logger
```

View logs:

```bash
docker compose logs -f logger processor nats
```

Stop all services:

```bash
docker compose down
```

Troubleshooting:
- If compose fails with `CHAT_IMAGE_TAGGER_TOOL_ROOT_HOST` error:
  - set a valid host path in `.env` for Eagle_AItagger_byWD1.4
- If `processor` cannot read image files:
  - ensure both `logger` and `processor` are mounting the same `chat-data` volume to `/app/data`
- If early messages are missing:
  - verify startup order and ensure `processor` subscription is ready before starting `logger`

Validation notes (2026-03-05):
- Unit tests: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` passed (`12/12`)
- Compose linting: `docker compose config` requires `.env` and `CHAT_IMAGE_TAGGER_TOOL_ROOT_HOST` value
- End-to-end runtime validation (`logger -> nats -> processor`) still requires real QQ bot credentials and a valid tagger tool path

### Manual/local fallback modes

```bash
python -m plugins.chat_image.tagger_cli
```

Only process one batch:

```bash
python -m plugins.chat_image.tagger_cli --once
```

## OTel + Signoz

- Enable OTel by setting `OTEL_ENABLED=true`.
- Traces and standard logging records are exported via OTLP gRPC.
- Unhandled Python/thread/asyncio exceptions are captured and emitted as error logs.
- Loguru logs are bridged into standard logging for unified OTLP log export.
- For Signoz default self-hosted collector, set:
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://<signoz-host>:4317`
  - `OTEL_EXPORTER_OTLP_INSECURE=true` (or `false` when TLS is enabled)
- Service identity in Signoz comes from:
  - `OTEL_SERVICE_NAME`
