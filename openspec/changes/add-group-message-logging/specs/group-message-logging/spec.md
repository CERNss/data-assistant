## ADDED Requirements

### Requirement: Log Group Message Events

系统 MUST 在收到群消息事件时，将结构化记录追加写入本地日志文件，至少包含事件标识、群标识、发送者标识、消息内容和原始事件载荷。

#### Scenario: Group message event is received

- **WHEN** 机器人在线且收到 `GroupAtMessageCreateEvent`
- **THEN** 系统将该事件写入 `data/group_messages.jsonl`
- **AND** 记录中包含 `group_openid`、`user_id`、`message_id`、`raw_event`

### Requirement: Log Group Delivery Notice Events

系统 MUST 在收到群接收/拒收通知事件时，将结构化记录追加写入通知日志文件。

#### Scenario: Group receive notice is received

- **WHEN** 机器人在线且收到 `GroupMsgReceiveEvent`
- **THEN** 系统将该事件写入 `data/group_notices.jsonl`
- **AND** 记录中包含 `group_openid`、`operator_openid`、`raw_event`

#### Scenario: Group reject notice is received

- **WHEN** 机器人在线且收到 `GroupMsgRejectEvent`
- **THEN** 系统将该事件写入 `data/group_notices.jsonl`
- **AND** 记录中包含 `group_openid`、`operator_openid`、`raw_event`

### Requirement: Do Not Claim Historical Backfill

系统 MUST 明确说明当前能力仅记录机器人在线后由平台推送的事件，不提供历史群消息回溯。

#### Scenario: User reads setup documentation

- **WHEN** 用户查看项目文档中的群消息记录说明
- **THEN** 能看到“仅支持在线后事件，不支持历史回溯”的限制说明
