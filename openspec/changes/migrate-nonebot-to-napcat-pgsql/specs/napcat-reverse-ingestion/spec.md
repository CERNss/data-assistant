## ADDED Requirements

### Requirement: Logger MUST Validate OneBot Basic Event Envelope
系统 MUST 在事件入口校验 OneBot 基础字段，确保后续解析和落库具有最小一致性。

#### Scenario: Basic envelope fields are present
- **WHEN** 收到任意入站事件
- **THEN** logger MUST 读取并校验 `time`、`self_id`、`post_type` 三个基础字段

#### Scenario: Unsupported envelope is rejected safely
- **WHEN** 事件缺少关键基础字段或格式非法
- **THEN** logger MUST 拒绝该事件并记录可追踪错误日志

### Requirement: Logger MUST Provide A Fixed Reverse WebSocket Endpoint For NapCat
系统 MUST 提供固定地址的反向 WebSocket 接入点供 NapCat 客户端主动连接，并按 OneBot11 协议接收事件。

#### Scenario: NapCat lifecycle connect event is accepted
- **WHEN** NapCat 连接 logger 端点并发送 `meta_event.lifecycle.connect`
- **THEN** logger MUST 接收事件并进入可持续消费状态

#### Scenario: Reverse endpoint can enforce token authentication
- **WHEN** 连接请求缺少或携带错误 token（在启用鉴权时）
- **THEN** logger MUST 拒绝该连接并记录鉴权失败

### Requirement: Logger MUST Handle OneBot Event Categories For Reverse Ingestion
系统 MUST 处理 OneBot 主要事件类别：`message`、`message_sent`、`notice`、`request`、`meta_event`。

#### Scenario: Message and message_sent are both accepted
- **WHEN** 收到 `post_type=message` 或 `post_type=message_sent`
- **THEN** logger MUST 按消息事件路径解析并进入统一处理流程

#### Scenario: Notice and request are ingested
- **WHEN** 收到 `post_type=notice` 或 `post_type=request`
- **THEN** logger MUST 接收并转入持久化与审计流程

### Requirement: Logger MUST Parse OneBot Message Events With Polymorphic Message Field
对于消息事件，系统 MUST 支持 `message` 字段为 segment 数组或 CQ 字符串两种形式，并优先使用结构化 segment。

#### Scenario: Private text message is parsed correctly
- **WHEN** 收到 `message_type=private` 且 `message` 为 segment 数组并包含 `text`
- **THEN** logger MUST 解析并产出发送者、消息文本和消息标识等标准字段

#### Scenario: Group message keeps group context fields
- **WHEN** 收到 `message_type=group` 的事件
- **THEN** logger MUST 保留 `group_id`、`group_name`、`sender.role` 与 `user_id` 等群上下文字段

#### Scenario: CQ string message is still accepted
- **WHEN** 收到消息事件且 `message` 字段为字符串（CQ 格式）
- **THEN** logger MUST 以该字符串作为可解析输入并保证事件不丢弃

### Requirement: Image URL Extraction MUST Prefer Structured Segment Data
系统 MUST 优先使用 `message[].data.url` 作为图片下载 URL；当结构化字段缺失时，MUST 兜底使用 `raw_message` CQ 解析。

#### Scenario: Structured image segment includes direct URL
- **WHEN** `message` 中存在 `type=image` 且 `data.url` 非空
- **THEN** logger MUST 使用该 URL 进入下载与后续处理流程

#### Scenario: Raw message fallback still works
- **WHEN** `message` 缺少可用 `image.data.url` 但 `raw_message` 含 `[CQ:image,...,url=...]`
- **THEN** logger MUST 通过 CQ 兜底提取 URL 并继续处理

### Requirement: Logger MUST Preserve Rich Image Segment Fields
系统 MUST 在接收图片 segment 时保留扩展字段，支持普通图片与商城/动画表情等变体。

#### Scenario: Standard image fields are retained
- **WHEN** 收到 `type=image` segment 且存在 `file`、`url`、`sub_type`、`file_size`
- **THEN** logger MUST 保留这些字段用于后续下载与落库

#### Scenario: Converted mface fields are retained
- **WHEN** 图片 segment 中存在 `key`、`emoji_id`、`emoji_package_id` 等扩展字段
- **THEN** logger MUST 保留这些字段在原始或结构化记录中，不得丢弃
