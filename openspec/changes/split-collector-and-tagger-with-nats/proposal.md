## Why

当前采集与打标逻辑仍可在同一进程内耦合运行，不利于独立扩缩容和故障隔离。将两者拆分为独立微服务并通过 NATS 解耦，可以稳定实现“采集服务只负责收集、打标服务只负责处理”。

## What Changes

- 将采集侧改为在图片保存成功后发布 NATS 消息，不再直接触发本地打标执行。
- 新增独立的打标消费者服务，订阅 NATS 消息并执行现有打标流水线。
- 引入 NATS 配置项（地址、主题、队列组、开关）并提供连接管理。
- 保留打标服务内部文件队列与重试机制，用于失败恢复和可观测性。
- 更新文档与测试，覆盖消息发布/消费路径与配置行为。

## Capabilities

### New Capabilities
- `nats-collector-tagger-services`: 采集与打标分离为两个微服务，通过 NATS 传递图片打标任务。

### Modified Capabilities
- `chat-image-tagger-pipeline`: 打标执行入口改为支持 NATS 消费驱动，保留本地队列和重试策略。

## Impact

- Affected code:
  - `plugins/chat_image/service.py`
  - `plugins/chat_image/config.py`
  - `plugins/chat_image/tagger_pipeline.py`
  - `README.md`
  - `requirements.txt`
  - `pyproject.toml`
- New code:
  - NATS 发布/订阅模块
  - 独立打标服务入口
- Runtime:
  - 需要可访问的 NATS 服务（如 `nats://127.0.0.1:4222`）
