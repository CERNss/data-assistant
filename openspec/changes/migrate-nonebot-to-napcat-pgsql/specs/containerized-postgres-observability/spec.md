## ADDED Requirements

### Requirement: Compose MUST Provide PostgreSQL Service For Logger Persistence
容器编排 MUST 提供 PostgreSQL 服务作为 logger 的主持久化存储，并开启持久卷。

#### Scenario: PostgreSQL service is defined with persistent storage
- **WHEN** 查看 compose 服务定义
- **THEN** 系统 MUST 包含数据库服务，且数据目录 MUST 挂载到持久化卷

#### Scenario: Logger can reach PostgreSQL via service network
- **WHEN** logger 在 compose 网络中启动
- **THEN** logger MUST 能通过服务发现地址连接 PostgreSQL

### Requirement: Compose MUST Provide Optional pgAdmin For Local Operations
系统 MUST 提供可选的 pgAdmin 服务用于本地开发和运维调试，并与 PostgreSQL 位于同一网络。

#### Scenario: pgAdmin depends on database service
- **WHEN** 启动 pgAdmin 服务
- **THEN** pgAdmin MUST 声明对数据库服务的依赖并共享网络

#### Scenario: pgAdmin credentials are configured through environment
- **WHEN** 查看 compose 环境变量配置
- **THEN** 系统 MUST 通过环境变量配置 pgAdmin 登录账号与密码

### Requirement: Existing NATS Processor Flow MUST Remain Intact After Compose Changes
新增数据库与管理服务后，系统 MUST 保持 `logger -> nats -> processor` 主链路不被破坏。

#### Scenario: Processor subscription path remains unchanged
- **WHEN** 查看 `processor` 的 NATS 连接配置
- **THEN** 其主题与队列配置 MUST 与迁移前保持兼容

#### Scenario: Logger still publishes image tasks after persistence
- **WHEN** logger 成功保存图片并写库
- **THEN** logger MUST 继续按既有协议发布任务到 NATS
