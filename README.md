# data-logger

## How to start

1. generate project using `nb create` .
2. install plugins using `nb plugin install` .
3. run your bot using `nb run` .

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
OTEL_SERVICE_NAME=data-logger
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
