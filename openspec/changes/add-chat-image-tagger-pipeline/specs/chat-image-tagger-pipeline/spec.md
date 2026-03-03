## ADDED Requirements

### Requirement: Collected Images SHALL Be Enqueued For Tagging
系统在图片采集成功并落盘后，必须将图片路径和消息上下文写入待打标队列，以支持异步“先收集后打标”流程。

#### Scenario: Enqueue on successful image save
- **WHEN** 聊天图片被成功下载并保存到本地路径
- **THEN** 系统 MUST 将该图片加入打标队列，并记录最小上下文（会话、消息、附件索引、来源 URL）

#### Scenario: No enqueue when image is not saved
- **WHEN** 图片下载或写盘失败
- **THEN** 系统 MUST NOT 将该图片加入打标队列

### Requirement: Tagger Queue Processor SHALL Support Retry And Auditing
系统必须提供队列消费执行器，支持批处理、失败重试与结果审计，确保打标处理可追踪且可恢复。

#### Scenario: Batch processing success
- **WHEN** 队列执行器成功完成一批图片打标
- **THEN** 系统 MUST 记录成功审计日志，包含图片路径、标签数量、标签内容和尝试次数

#### Scenario: Retry before max attempts
- **WHEN** 某图片打标失败且尝试次数未达到最大值
- **THEN** 系统 MUST 将该图片重新入队并记录 `retrying` 审计状态

#### Scenario: Final failure after max attempts
- **WHEN** 某图片打标失败且尝试次数达到最大值
- **THEN** 系统 MUST 记录 `failed` 审计状态并停止重试该图片

### Requirement: Integration SHALL Be Backward Compatible And Configurable
打标能力必须由配置显式开启，默认关闭；当未开启时，系统行为必须与原有采集流程一致。

#### Scenario: Disabled by default
- **WHEN** 未设置或关闭打标开关
- **THEN** 系统 MUST 继续仅执行图片采集与采集审计，不触发打标执行

#### Scenario: Manual queue processing
- **WHEN** 运维执行打标 CLI
- **THEN** 系统 MUST 消费队列并输出批次摘要（picked/success/failed/requeued/pending）
