## Why

当前 `onebot_events` 表存了所有类型的事件（heartbeat、notice、message 等），消息内容和发送者信息埋在 `raw` JSONB 字段中。想按人或按群组导出聊天记录时，需要手写复杂的 JSON 查询，既不直观也不高效。

需要一张专门的消息表，从 `post_type=message` 和 `post_type=message_sent` 的事件中提取结构化字段（发送者昵称/群名片、消息文本、群组信息等），支持按 `user_id` 或 `group_id` 快速筛选和导出。

## What Changes

- 新增 `onebot_messages` 表，从消息事件中提取结构化字段：sender_nickname、sender_card、sender_role、plain_text（纯文本内容）、message_segments（JSONB）等。
- 在持久化 pipeline 中，当事件为 `message` 或 `message_sent` 类型时，同步写入 `onebot_messages` 表。
- 新增导出 CLI 命令，支持按 `user_id`、`group_id`、时间范围筛选并导出为 JSONL 文件。

## Capabilities

### New Capabilities

- `structured-message-storage`: 从 OneBot 消息事件中提取结构化字段，持久化到专用 `onebot_messages` 表，支持按人/按群索引。
- `message-export-cli`: CLI 工具，按 user_id / group_id / 时间范围查询消息并导出为 JSONL。

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- **logger_service/service/persistence/db.py**：新增 `onebot_messages` 表 DDL。
- **logger_service/service/persistence/repository.py**：新增 `insert_message()` 函数。
- **logger_service/service/napcat/pipeline.py**：`persist_event` 增加消息写入逻辑。
- **新增 CLI 模块**：`logger_service/service/export.py` 或类似位置，提供命令行导出能力。
- **无新依赖**：asyncpg 已在使用中。
