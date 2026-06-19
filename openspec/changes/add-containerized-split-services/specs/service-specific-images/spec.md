## ADDED Requirements

### Requirement: Logger And Processor MUST Be Built As Separate Images
系统必须为 `logger` 与 `processor` 提供独立镜像构建定义，确保两个服务可独立构建、独立发布、独立回滚。

#### Scenario: Logger image build definition exists
- **WHEN** 查看容器构建文件
- **THEN** 系统 MUST 存在专用于 `logger` 的镜像构建定义

#### Scenario: Processor image build definition exists
- **WHEN** 查看容器构建文件
- **THEN** 系统 MUST 存在专用于 `processor` 的镜像构建定义

### Requirement: Each Service Image MUST Start Only Its Own Entrypoint
每个服务镜像在运行时必须仅启动对应服务入口，不得在单个容器中同时运行采集与处理流程。

#### Scenario: Logger image starts collector entrypoint
- **WHEN** 启动 `logger` 服务容器
- **THEN** 容器 MUST 仅执行采集服务入口（`data_logger_service.py` 或等价入口）

#### Scenario: Processor image starts processor entrypoint
- **WHEN** 启动 `processor` 服务容器
- **THEN** 容器 MUST 仅执行处理服务入口（`data_processor_service.py` 或等价入口）

#### Scenario: No mixed process in one service container
- **WHEN** 任一服务容器启动完成
- **THEN** 容器内 MUST NOT 同时运行采集入口与处理入口

### Requirement: Runtime Configuration MUST Preserve Service Responsibility Boundaries
容器运行配置必须明确服务职责边界：`logger` 负责采集发布，`processor` 负责消费处理。

#### Scenario: Logger runtime disables local processor behavior
- **WHEN** 启动 `logger` 容器
- **THEN** 运行配置 MUST 使其仅承担采集职责，且不在同容器内触发处理服务入口

#### Scenario: Processor runtime enables task consumption behavior
- **WHEN** 启动 `processor` 容器
- **THEN** 运行配置 MUST 使其订阅并消费 NATS 任务消息
