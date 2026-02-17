## Why

当前机器人只写本地日志，缺少统一可观测能力，无法在 Signoz 中查看端到端 trace 和聚合日志。  
需要接入 OpenTelemetry（OTel）并通过 OTLP 导出到 Signoz，用于问题定位和运行监控。

## What Changes

- 新增 OTel 初始化模块，支持 Trace 与 Log 导出。
- 启动流程接入 OTel 初始化，可通过环境变量开关控制。
- 群消息/图片下载逻辑补充关键 span，覆盖核心处理链路。
- 文档新增 Signoz 接入示例和配置项说明。
- 增加 OTel 依赖到项目配置。

## Capabilities

### New Capabilities
- `otel-observability`: 支持将应用 trace 与日志通过 OTLP 导出到 Signoz。

### Modified Capabilities
- `group-image-archiving`: 增加图片下载处理链路追踪 span 与异常标记。

## Impact

- `bot.py`: 启动阶段注入 OTel 初始化。
- `plugins/group_logger.py`: 增加 trace span。
- `pyproject.toml`: 增加 OTel SDK/Exporter 依赖。
- `README.md`: 新增 Signoz 配置说明。
