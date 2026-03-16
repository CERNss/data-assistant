## ADDED Requirements

### Requirement: Messages table schema
系统 SHALL 创建 `onebot_messages` 表，包含以下列：
- `id` bigserial PRIMARY KEY
- `event_id` bigint NOT NULL REFERENCES onebot_events(id) ON DELETE CASCADE
- `message_type` text NOT NULL（"private" 或 "group"）
- `user_id` bigint NOT NULL
- `group_id` bigint（私聊为 NULL）
- `group_name` text（私聊为 NULL）
- `sender_nickname` text
- `sender_card` text（群名片，私聊为 NULL）
- `sender_role` text（群角色 owner/admin/member，私聊为 NULL）
- `message_id` text
- `plain_text` text（从 message segments 中提取的纯文本拼接）
- `message_segments` jsonb（完整 message 段数组）
- `event_time` timestamptz NOT NULL
- `created_at` timestamptz NOT NULL DEFAULT now()

系统 SHALL 创建以下索引：
- `idx_onebot_messages_user_id` ON (user_id)
- `idx_onebot_messages_group_id` ON (group_id)
- `idx_onebot_messages_event_time` ON (event_time)

#### Scenario: Table created on init_db
- **WHEN** logger_service 启动并调用 `init_db()`
- **THEN** `onebot_messages` 表被创建（IF NOT EXISTS）
- **THEN** 所有索引被创建

#### Scenario: Foreign key constraint enforced
- **WHEN** 插入一条 `event_id` 不存在于 `onebot_events` 的消息记录
- **THEN** 插入失败并抛出外键约束异常

### Requirement: Persist message on event receipt
当 `persist_event()` 处理的事件 `post_type` 为 `message` 或 `message_sent` 时，系统 SHALL 在写入 `onebot_events` 之后，额外将结构化消息写入 `onebot_messages` 表。

`plain_text` 的提取规则：
- 若 `message_segments` 可用，拼接所有 `type=text` 段的 `data.text` 值
- 若仅有 CQ 格式字符串，使用 `raw_message` 作为 `plain_text`

`sender_nickname`、`sender_card`、`sender_role` 从 `event.sender` dict 中提取，字段不存在时存 NULL。

#### Scenario: Group message persisted
- **WHEN** 收到一条 `post_type=message`、`message_type=group` 的事件
- **THEN** `onebot_events` 表插入一行
- **THEN** `onebot_messages` 表插入一行，`group_id` 非空，`sender_card` 和 `sender_role` 从 sender dict 提取

#### Scenario: Private message persisted
- **WHEN** 收到一条 `post_type=message`、`message_type=private` 的事件
- **THEN** `onebot_messages` 表插入一行，`group_id` 为 NULL，`sender_card` 为 NULL，`sender_role` 为 NULL

#### Scenario: Bot sent message persisted
- **WHEN** 收到一条 `post_type=message_sent` 的事件
- **THEN** `onebot_messages` 表插入一行，`user_id` 为 bot 自身的 `self_id`

#### Scenario: Non-message event ignored
- **WHEN** 收到 `post_type=notice` 或 `post_type=meta_event` 的事件
- **THEN** `onebot_messages` 表无新行插入

#### Scenario: Plain text extracted from segments
- **WHEN** 消息包含 `[{type:text, data:{text:"hello "}}, {type:image, ...}, {type:text, data:{text:"world"}}]`
- **THEN** `plain_text` 为 `"hello world"`

#### Scenario: Plain text fallback to raw_message
- **WHEN** 消息仅有 CQ 格式字符串（无 array segments）
- **THEN** `plain_text` 为 `raw_message` 的值

#### Scenario: Message persistence failure does not crash service
- **WHEN** `onebot_messages` 插入失败（如 DB 异常）
- **THEN** 错误被 logger.error 记录
- **THEN** 服务继续运行，不影响后续事件处理
- **THEN** `onebot_events` 的写入不受影响（已提前完成）
