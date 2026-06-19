## ADDED Requirements

### Requirement: Project Identity SHALL Use data-assistant
项目对外标识（项目元数据与默认运行标识）必须统一到 `data-assistant` 命名体系。

#### Scenario: Package metadata naming
- **WHEN** 查看项目元数据配置
- **THEN** 项目名称 MUST 为 `data-assistant`

#### Scenario: Runtime default naming
- **WHEN** 未显式设置服务名相关环境变量
- **THEN** 默认 NATS client name 与默认 OTel service name MUST 使用 `data-assistant` 命名

### Requirement: System SHALL Provide Two Explicit Service Entrypoints
系统必须提供采集服务和处理服务两个顶层入口，便于独立部署。

#### Scenario: Start collector service
- **WHEN** 执行采集服务入口脚本
- **THEN** 系统 MUST 启动消息采集服务

#### Scenario: Start processor service
- **WHEN** 执行处理服务入口脚本
- **THEN** 系统 MUST 启动打标处理服务
