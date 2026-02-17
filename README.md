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
GROUP_IMAGE_SAVE_DIR=data/group_images
GROUP_IMAGE_TIMEOUT_SEC=20
```

Note: the bot can only log events pushed by QQ platform after the bot is online and has permissions. It cannot read chat history retroactively.

## Group Image Archiving

- Images in group message attachments are downloaded and saved under:
  - `<GROUP_IMAGE_SAVE_DIR>/<YYYY-MM-DD>/<group_openid>/`
- Audit log is written to:
  - `data/group_images.jsonl`
- Quality strategy:
  - The bot downloads the attachment URL as-is (no compression/transcoding), preserving the best quality available from QQ attachment URL.
