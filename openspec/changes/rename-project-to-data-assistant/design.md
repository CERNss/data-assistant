## Context

当前仓库已支持两微服务架构，但入口运行方式分散在模块路径，项目名也与当前定位不一致。目标是保持功能不变前提下，完成命名统一和启动标准化。

## Goals / Non-Goals

**Goals:**
- 统一项目名为 `data-assistant`。
- 明确两个服务入口，降低运维和文档歧义。
- 同步默认运行标识（OTEL/NATS）以匹配新命名。

**Non-Goals:**
- 不改变采集/处理核心业务逻辑。
- 不调整 NATS 消息结构或处理策略。

## Decisions

1. 项目包名改为 `data-assistant`
- 在 `pyproject.toml` 修改 `name` 与 `description`，并新增 console scripts。

2. 保留 `data-logger` / `data-processor` 作为服务角色名
- 项目名与服务角色分离：项目统一为 `data-assistant`，服务角色在文档中继续叫 `data-logger` 和 `data-processor`。

3. 新增顶层入口脚本
- 使用 `data_logger_service.py` 与 `data_processor_service.py` 作为最直接运行入口。

## Risks / Trade-offs

- [命名迁移不彻底] 文档/默认值残留旧名  
  → Mitigation: 同步更新 README、OTEL 默认值、NATS client 默认值和测试断言。

- [入口兼容性] 旧运行命令与新入口并存可能造成短期混淆  
  → Mitigation: README 优先展示新入口，旧方式仍可兼容。
