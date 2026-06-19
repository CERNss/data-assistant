## ADDED Requirements

### Requirement: CLI export command
系统 SHALL 提供 CLI 命令 `python3 -m logger_service.service.export`，从 `onebot_messages` 表查询消息并输出 JSONL 格式。

支持的筛选参数：
- `--user-id <id>`：按发送者 user_id 筛选
- `--group-id <id>`：按群组 group_id 筛选
- `--from <date>`：起始时间（ISO 8601 或 YYYY-MM-DD）
- `--to <date>`：结束时间（ISO 8601 或 YYYY-MM-DD）
- `--output <path>`：输出文件路径（默认 stdout）
- `--limit <n>`：最大导出条数

至少须指定 `--user-id` 或 `--group-id` 之一。

每行 JSON 输出 SHALL 包含：`message_type`、`user_id`、`group_id`、`group_name`、`sender_nickname`、`sender_card`、`plain_text`、`event_time`、`message_id`。

#### Scenario: Export by user_id
- **WHEN** 执行 `python3 -m logger_service.service.export --user-id 12345 --output chat.jsonl`
- **THEN** 输出文件包含所有 `user_id=12345` 的消息记录，按 `event_time` 升序排列
- **THEN** 每行是一个合法 JSON 对象

#### Scenario: Export by group_id with time range
- **WHEN** 执行 `python3 -m logger_service.service.export --group-id 67890 --from 2026-03-01 --to 2026-03-15`
- **THEN** 输出仅包含该群在指定时间范围内的消息

#### Scenario: Export to stdout
- **WHEN** 未指定 `--output` 参数
- **THEN** JSONL 输出到 stdout

#### Scenario: No filter provided
- **WHEN** 既未指定 `--user-id` 也未指定 `--group-id`
- **THEN** 命令报错并提示至少须指定一个筛选条件

#### Scenario: Export with limit
- **WHEN** 指定 `--limit 100`
- **THEN** 最多输出 100 条记录

#### Scenario: Empty result
- **WHEN** 查询条件匹配零条记录
- **THEN** 输出为空（0 字节），命令正常退出（exit code 0）
