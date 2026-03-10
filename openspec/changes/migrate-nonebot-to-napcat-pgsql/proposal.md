## Why

当前 `data-logger` 依赖 NoneBot QQ 官方适配器作为事件入口，难以直接复用 NapCat 的 OneBot11 数据源。团队需要切换为 NapCat 作为客户端、由 `data-logger` 提供固定反向 WebSocket 接入点，并将采集到的全部关键数据持久化到 PostgreSQL，以支撑后续查询、审计和扩展分析。

## What Changes

- 新增基于 NapCat OneBot11 反向 WebSocket（NapCat 主动连接 `data-logger`）的采集入口，替代现有 NoneBot 运行时入口。
- 在采集侧解析消息事件、通知事件与元事件，并统一落库到 PostgreSQL。
- 为图片采集链路增加数据库记录：原始事件、图片元数据、下载结果、NATS 投递状态等，形成可追踪闭环。
- 保留现有图片下载与 NATS 投递后续流程，继续由 `data-processor` 消费并执行打标。
- 更新容器编排，新增 PostgreSQL（可选 pgAdmin）并完成 logger/processor 与数据库网络和配置联通。
- **BREAKING**: 移除/弃用基于 NoneBot QQ 官方适配器的 `data-logger` 启动与配置方式（例如 `QQ_BOTS`、NoneBot driver 相关配置），迁移到 NapCat 连接配置。

## Capabilities

### New Capabilities
- `napcat-reverse-ingestion`: 使用 NapCat 反向 WebSocket 持续接收 OneBot11 事件并进行基础路由处理。
- `event-persistence-pgsql`: 将采集事件和处理状态结构化持久化到 PostgreSQL，并保证可查询与可审计。
- `containerized-postgres-observability`: 在 Docker Compose 中提供 PostgreSQL 与可选 pgAdmin 管理入口，支持本地/容器化运维。

### Modified Capabilities
- 无。

## Impact

- Affected code:
  - `data_logger_service.py`
  - `bot.py`（可能降级为兼容入口或移除 logger 主路径）
  - `plugins/group_logger.py`（由 NapCat 事件处理模块替代）
  - `plugins/chat_image/service.py`（适配 NapCat 消息模型输入）
  - `plugins/chat_image/nats_task_bus.py`
  - `plugins/chat_image/config.py`
  - `docker-compose.yml`
  - `.env.example`
  - `requirements.txt`
  - `pyproject.toml`
- New code/modules (planned):
  - `plugins/napcat/`（连接、事件解析、路由处理）
  - `plugins/persistence/` 或等效模块（PostgreSQL schema/init 与 repository）
- Data systems:
  - 新增 PostgreSQL 数据库表（事件主表、图片记录表、投递状态表等，最终字段将结合用户后续提供的数据样例在 design/specs 阶段固化）。
- Runtime/deployment:
  - `logger` 运行依赖从 NoneBot 迁移到 NapCat OneBot11 WS + PostgreSQL。
  - `processor` 主职责保持不变，继续消费 NATS 并执行后续打标逻辑。
