## Context

项目目前以 NoneBot 插件方式运行，核心逻辑在消息事件处理器内，尚无统一可观测框架。

## Goals

- 快速接入 Signoz 所需 OTel Trace + Log 导出。
- 保持对现有业务逻辑低侵入。
- 通过环境变量完成配置，方便本地与生产切换。

## Non-Goals

- 不在本次引入 metrics。
- 不实现复杂采样策略与多后端导出。

## Approach

1. 新增 `telemetry.py`：
   - 初始化 `TracerProvider` + `OTLPSpanExporter`。
   - 初始化 `LoggerProvider` + `OTLPLogExporter`。
   - 给 root logger 增加 `LoggingHandler`。
   - 安装全局异常钩子（`sys`/`threading`/`asyncio`）输出错误日志。
   - 将 loguru 日志桥接到标准 logging，统一走 OTel Log 导出。
2. 在 `bot.py` 启动时调用 `init_telemetry()`。
3. 在 `plugins/group_logger.py` 中为关键流程添加 span：
   - 群消息处理 span
   - 私聊消息处理 span
   - 图片下载重试 span
4. 配置项通过环境变量读取：
   - `OTEL_ENABLED`
   - `OTEL_SERVICE_NAME`
   - `OTEL_EXPORTER_OTLP_ENDPOINT`
   - `OTEL_EXPORTER_OTLP_INSECURE`
   - `OTEL_EXPORTER_OTLP_HEADERS`

## Risks

- 端点/证书配置错误会导致导出失败，需要从本地日志排查。
