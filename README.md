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
```

Note: the bot can only log events pushed by QQ platform after the bot is online and has permissions. It cannot read chat history retroactively.
