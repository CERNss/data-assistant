## ADDED Requirements

### Requirement: Configurable OTel Bootstrap

系统 MUST 支持通过环境变量开启/关闭 OTel，并配置 OTLP 导出端点和服务名。

#### Scenario: OTel enabled with endpoint

- **WHEN** `OTEL_ENABLED=true` 且配置了 OTLP 端点
- **THEN** 系统初始化 trace provider 与 log provider
- **AND** 导出目标为配置的 OTLP 端点

#### Scenario: OTel disabled

- **WHEN** `OTEL_ENABLED=false`
- **THEN** 系统不初始化 OTel provider
- **AND** 应用保持原有运行行为

### Requirement: Export Traces To Signoz

系统 MUST 将关键业务链路作为 trace span 输出，便于在 Signoz 中查看调用路径和错误。

#### Scenario: Group message processing traced

- **WHEN** 机器人处理群消息事件
- **THEN** 系统创建对应 span 并附带群/消息标识属性

#### Scenario: Image download traced

- **WHEN** 机器人下载图片附件
- **THEN** 系统创建下载 span
- **AND** 失败时设置 error 状态并记录异常信息

### Requirement: Export Logs Via OTel

系统 MUST 将标准 logging 日志通过 OTel Log 导出到 OTLP 端点。

#### Scenario: Application emits logging records

- **WHEN** 应用产生标准 logging 日志
- **THEN** 日志被 OTLP 日志导出器发送到配置端点

### Requirement: Collect Error Logs For Unhandled Exceptions

系统 MUST 捕获未处理异常并输出错误日志，以便在 Signoz 中检索故障。

#### Scenario: Unhandled runtime exception occurs

- **WHEN** 主线程、子线程或 asyncio 任务出现未捕获异常
- **THEN** 系统记录错误日志并附带异常堆栈
- **AND** 错误日志通过 OTLP 导出到配置端点
