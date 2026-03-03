## Why

项目已拆分为采集与处理两个独立服务，但项目标识仍沿用旧命名，启动入口也不够直观，影响部署和运维沟通。需要统一重命名为 `data-assistant` 并补齐清晰的双服务入口。

## What Changes

- 将项目元数据名从 `data-logger` 统一为 `data-assistant`。
- 新增两个顶层服务入口脚本：
  - `data_logger_service.py`（collector / data-logger）
  - `data_processor_service.py`（processor / data-processor）
- 调整默认配置名称（NATS client name、OTEL 默认 service name）以匹配新项目名。
- 更新 README 启动方式与环境示例。

## Capabilities

### New Capabilities
- `project-identity-and-service-entrypoints`: 提供统一项目命名与双服务标准启动入口。

### Modified Capabilities
- 无。

## Impact

- Affected code:
  - `pyproject.toml`
  - `README.md`
  - `telemetry.py`
  - `plugins/chat_image/config.py`
  - `bot.py`
  - `tests/test_chat_image_config.py`
- New files:
  - `data_logger_service.py`
  - `data_processor_service.py`
