## ADDED Requirements

### Requirement: System MUST Persist Every Inbound OneBot Event To PostgreSQL
系统 MUST 将每条入站 OneBot 事件写入 PostgreSQL，并同时保存原始 payload 与关键索引字段。

#### Scenario: Message event is stored with raw payload and parsed columns
- **WHEN** 收到任意 `post_type=message` 事件
- **THEN** 系统 MUST 在事件主表中保存 `raw` JSON、`post_type`、`message_type`、`self_id`、`user_id`、`message_id`、`time`、`raw_message` 以及群聊可用的 `group_id`/`group_name`

#### Scenario: Message sent event is also persisted
- **WHEN** 收到 `post_type=message_sent` 事件
- **THEN** 系统 MUST 按消息事件等价字段写入主表并区分 `post_type=message_sent`

#### Scenario: Meta event is still persisted for connection observability
- **WHEN** 收到 `post_type=meta_event`（例如 lifecycle/heartbeat）
- **THEN** 系统 MUST 持久化该事件并保留原始 payload 以支持连接健康审计

#### Scenario: Notice and request events are persisted
- **WHEN** 收到 `post_type=notice` 或 `post_type=request`
- **THEN** 系统 MUST 持久化事件并保留其类型特有字段在 `raw` JSON 中

### Requirement: System MUST Store Event Time Semantics Correctly
系统 MUST 按协议语义保存时间字段，避免秒/毫秒单位混淆。

#### Scenario: Event timestamp uses seconds
- **WHEN** 解析事件基础字段 `time`
- **THEN** 系统 MUST 将其按 Unix 秒级时间戳解释并写入可查询时间列

#### Scenario: Heartbeat interval keeps millisecond unit
- **WHEN** 解析 `meta_event_type=heartbeat` 事件
- **THEN** 系统 MUST 按毫秒单位保留 `interval` 原值并写入原始 payload

### Requirement: System MUST Persist Image Extraction And Download Outcomes
对于消息中的图片段，系统 MUST 按“一图一记录”持久化提取结果与下载结果。

#### Scenario: Image download success is recorded
- **WHEN** 消息中解析到图片 URL 且下载成功
- **THEN** 系统 MUST 记录图片原始 URL、解码 URL、本地保存路径、文件大小和成功状态

#### Scenario: Image download failure is recorded
- **WHEN** 消息中解析到图片 URL 但下载失败
- **THEN** 系统 MUST 记录失败状态与错误信息，且保留关联事件 ID 与图片序号

### Requirement: System MUST Persist Image Binary Metadata And Dedup Evidence
系统 MUST 在图片下载后记录可用于质量分析与去重的二进制元数据。

#### Scenario: Downloaded image metadata is captured
- **WHEN** 图片下载成功且可读取二进制内容
- **THEN** 系统 MUST 记录哈希值、格式、宽高、是否动图、帧数与 HTTP 响应关键信息（如 Content-Type/Content-Length）

#### Scenario: Duplicate image is detected and persisted
- **WHEN** 新下载图片与已处理图片哈希一致
- **THEN** 系统 MUST 记录重复状态与对应哈希证据，并避免重复写入同一原图文件

### Requirement: System MUST Handle Image URL Expiration And File Retrieval Fallback
系统 MUST 处理 NapCat 图片 URL 过期场景，并具备协议兼容的兜底刷新/获取策略。

#### Scenario: URL expired is handled with refresh strategy
- **WHEN** 图片下载返回 URL 过期或同类可识别错误
- **THEN** 系统 MUST 触发刷新直链或文件重新获取流程（例如基于协议支持的 `nc_get_rkey`、`get_image`、`get_file`、`get_msg`）并记录尝试结果

#### Scenario: Fallback exhaustion is recorded
- **WHEN** 直链刷新或文件兜底流程全部失败
- **THEN** 系统 MUST 记录最终失败状态与失败阶段，确保后续可重试

### Requirement: System MUST Support Chunk-Aware Media Transfer Path
系统 MUST 为大文件或跨设备场景保留分片/流式传输兼容路径，不依赖单一整包下载假设。

#### Scenario: Stream transfer progress is representable
- **WHEN** 使用 NapCat Stream API 下载或上传文件
- **THEN** 系统 MUST 能识别并记录 `stream` 过程状态与 `response/error` 终态

#### Scenario: Non-stream path remains valid
- **WHEN** 文件可通过常规 URL 一次性下载
- **THEN** 系统 MUST 允许走常规路径且不要求强制分片

### Requirement: System MUST Persist NATS Dispatch Status For Downstream Continuity
图片消息进入下游前，系统 MUST 记录 NATS 投递状态，确保从采集到处理链路可追踪。

#### Scenario: Publish succeeds
- **WHEN** 图片任务成功发布到 NATS
- **THEN** 系统 MUST 写入投递记录并标记状态为成功

#### Scenario: Publish fails or falls back
- **WHEN** NATS 发布失败或触发本地兜底队列
- **THEN** 系统 MUST 写入对应失败/兜底状态和错误详情
