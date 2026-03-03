## ADDED Requirements

### Requirement: Collector Service MUST Publish Tagging Tasks To NATS
采集服务在图片保存成功后必须向 NATS 发布打标任务消息，消息需包含图片路径与最小上下文信息。

#### Scenario: Publish task after successful image save
- **WHEN** 采集服务成功保存一张聊天图片
- **THEN** 系统 MUST 向配置的 NATS subject 发布包含 `image_path` 和 `context` 的 JSON 消息

#### Scenario: Do not publish for failed image save
- **WHEN** 图片下载或写盘失败
- **THEN** 系统 MUST NOT 发布打标任务消息

### Requirement: Tagger Worker MUST Consume NATS Tasks Independently
打标服务必须可作为独立进程运行，订阅 NATS 主题并消费打标任务，而不依赖采集服务进程内执行。

#### Scenario: Worker consumes published tasks
- **WHEN** NATS 上出现合法打标任务消息
- **THEN** 打标服务 MUST 解析消息并将任务送入打标执行队列

#### Scenario: Worker keeps running on malformed messages
- **WHEN** 收到格式错误的消息
- **THEN** 打标服务 MUST 记录错误并继续处理后续消息
