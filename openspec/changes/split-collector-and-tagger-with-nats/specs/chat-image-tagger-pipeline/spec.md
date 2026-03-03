## MODIFIED Requirements

### Requirement: Collected Images SHALL Be Enqueued For Tagging
系统在图片采集成功并落盘后，必须将图片路径和消息上下文交给打标处理链路。链路必须支持两种模式：
1) NATS 发布模式（采集服务发布到 NATS，由独立打标服务消费）；
2) 本地入队模式（未启用 NATS 时回退）。

#### Scenario: Use NATS publish mode when enabled
- **WHEN** 采集服务启用了 NATS 发布配置且图片保存成功
- **THEN** 系统 MUST 优先发布打标任务到 NATS，而不是在采集进程内直接执行打标

#### Scenario: Fallback to local enqueue when NATS disabled
- **WHEN** 采集服务未启用 NATS 发布
- **THEN** 系统 MUST 使用本地入队方式保持“先收集后打标”能力
