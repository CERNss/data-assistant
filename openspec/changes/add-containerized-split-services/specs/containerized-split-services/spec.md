## ADDED Requirements

### Requirement: System MUST Provide A Compose Topology For Logger/NATS/Processor
系统必须提供一个可执行的 Docker Compose 拓扑，统一编排 `logger`、`nats`、`processor` 三个服务，支持一键启动与联调。

#### Scenario: Compose defines three runtime services
- **WHEN** 查看容器编排配置
- **THEN** 系统 MUST 定义 `logger`、`nats`、`processor` 三个服务且可由同一个 compose 文件启动

#### Scenario: NATS uses official image
- **WHEN** 查看 `nats` 服务定义
- **THEN** 系统 MUST 使用官方 NATS 镜像而非项目自建镜像

### Requirement: Logger And Processor MUST Share One Volume At The Same Mount Path
采集服务与处理服务必须共享同一个持久化卷，并在容器内挂载到相同路径，以保证消息中的文件路径在处理侧可直接访问。

#### Scenario: Shared data volume is mounted consistently
- **WHEN** 查看 `logger` 与 `processor` 的卷挂载配置
- **THEN** 两个服务 MUST 挂载同一命名卷且容器内目标路径 MUST 完全一致

#### Scenario: Saved image path is readable by processor
- **WHEN** `logger` 侧保存图片并发布包含 `image_path` 的任务消息
- **THEN** `processor` 侧 MUST 能在该路径读取到对应图片文件

### Requirement: Services MUST Communicate Through A Shared Compose Network
三个服务必须在同一个编排网络中通信，业务服务连接 NATS 时必须使用服务发现地址而非宿主机硬编码地址。

#### Scenario: Service discovery uses NATS service name
- **WHEN** 检查业务服务的 NATS 连接配置
- **THEN** 系统 MUST 使用 `nats://nats:4222`（或等价的服务名地址）进行连接

#### Scenario: Startup guidance prioritizes consumer readiness
- **WHEN** 按文档执行首次启动
- **THEN** 文档 MUST 要求先启动 `nats` 与 `processor`，再启动 `logger` 以降低消息丢失窗口
