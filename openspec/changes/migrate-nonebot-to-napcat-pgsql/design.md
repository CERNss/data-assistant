## Context

当前采集入口依赖 NoneBot + QQ 官方适配器，事件处理与运行时生命周期绑定在 `bot.py`/`plugins/group_logger.py`。在目标方案中，NapCat 作为 OneBot11 客户端主动连接 `data-logger` 的固定反向 WebSocket 地址，`data-logger` 负责接收事件、解析消息、下载图片、写入 PostgreSQL，并继续沿用现有 NATS + `data-processor` 打标链路。

基于已提供的真实样例，已确认私聊与群聊事件核心字段包括：
- 顶层：`post_type`、`message_type`、`self_id`、`user_id`、`time`、`message_id`、`raw_message`、`message`、`target_id`
- 群聊扩展：`group_id`、`group_name`、`sender.role`、`sub_type=normal`
- `message_format` 为 `array`，`message` 为 segment 数组（例如 `text`/`face`/`image`）
- 图片 segment 在 `message[].data.url` 中提供可直接下载的 URL（已解码 `&`），`raw_message` 中则可能含 HTML 实体 `&amp;`

参照 NapCat OneBot11 文档（`/onebot/basic_event`）后，采集层还需满足以下协议事实：
- 所有事件基础字段为 `time`（秒）、`self_id`、`post_type`
- `post_type` 需要覆盖 `message`、`message_sent`、`notice`、`request`、`meta_event`
- `message` 字段存在多态（segment 数组或字符串 CQ），解析必须兼容
- `meta_event.heartbeat.interval` 为毫秒单位，需与 `time` 秒级语义区分
- 图片 `image.data.url` 存在过期窗口（文档约 2 小时），超时后需通过 `get_image`/`get_file`/`get_msg` 或 `nc_get_rkey` 刷新
- NapCat v4.8.115+ 提供 Stream API（`download_file_stream`/`upload_file_stream`），需考虑流式分片状态上报

约束与前提：
- 需要保持现有 `data-processor` 与 NATS 消费行为不变。
- 需要在 PostgreSQL 中保留“全量原始事件 + 可检索字段 + 图片下载/投递状态”。
- 需要支持容器化部署并提供数据库运维入口（pgAdmin 可选但默认启用）。

## Goals / Non-Goals

**Goals:**
- 以反向 WebSocket 模式接入 NapCat（NapCat 主动连接，logger 固定地址）。
- 用 PostgreSQL 承载采集侧全量事件与处理状态，支持审计与查询。
- 保留并复用当前图片下载、NATS 发布、processor 打标链路。
- 在 Docker Compose 中纳入 PostgreSQL 与 pgAdmin，形成可一键联调拓扑。

**Non-Goals:**
- 不改造 `data-processor` 的任务消费协议与打标算法。
- 不在本变更中引入 JetStream 持久化语义变更。
- 不在本变更中实现历史日志回灌/全量补数。
- 不依赖 `raw_message` 正则作为唯一解析来源（仅作为兜底）。

## Decisions

1. 连接模式采用 NapCat 反向 WebSocket（Reverse WS）
- 决策：`data-logger` 启动 WS 服务端，NapCat 作为客户端连接；logger 地址固定，NapCat 通过配置回连。
- 原因：满足“logger 连接地址固定”的运维诉求，便于在容器和内网环境稳定发布。
- 备选：
  - 正向 WS（logger 主动连 NapCat）：实现简单，但 logger 连接目标会随 NapCat 部署位置变化，不符合当前诉求。

2. 事件解析以 `message` 数组为主，`raw_message` 正则为兜底
- 决策：优先读取 `message_format=array` 下的 segment 数据；仅当缺失或异常时，使用 `raw_message` CQ 正则提取图片 URL。
- 原因：segment 结构化字段更稳定（尤其 `image.data.url` 已去 HTML 实体）。
- 备选：
  - 全量依赖 `raw_message` 正则：对转义、字段顺序、混合 segment 更脆弱。

3. PostgreSQL 采用“原始事件主表 + 明细子表”结构
- 决策：
  - `onebot_events`：保存每条入站事件原始 JSONB 与常用索引列。
  - `onebot_message_images`：保存消息中的图片段、下载结果与本地路径。
  - `onebot_nats_dispatches`：保存图片任务投递 NATS 的请求载荷与状态。
- 原因：兼顾全量保真、查询效率与后续 schema 演进能力。
- 备选：
  - 单表 JSONB：实现快但查询成本高，审计和状态追踪不友好。
  - 强规范化拆多表：复杂度高，不利于早期迭代。

4. 采集侧写库优先，后续流程复用既有模块
- 决策：消息入站后先写 `onebot_events`，图片消息再执行下载并写图片表，最后调用现有 NATS 发布逻辑并写 dispatch 状态。
- 原因：数据库成为事实来源（source of truth），并保持 processor 无感迁移。
- 备选：
  - 先发 NATS 后写库：在失败路径中更难做一致性追踪。

5. 迁移策略采用“入口替换 + 配置切换”，保留旧代码短期兼容
- 决策：新增 NapCat logger 入口，替换 compose 启动命令；旧 NoneBot 入口可短期保留但不作为默认路径。
- 原因：降低切换风险，便于回滚。
- 备选：
  - 立即删除 NoneBot 路径：回滚成本高。

6. 协议分类不裁剪，统一全量入库
- 决策：除了 `message`，还要对 `message_sent`、`notice`、`request`、`meta_event` 进行统一持久化。
- 原因：避免早期丢失治理与审计上下文，支持后续功能扩展（如撤回、入群请求审计）。
- 备选：
  - 仅落 `message`：实现简化，但会丢失连接健康和系统通知事件，排障能力不足。

7. 图片处理采用“即时下载 + 元数据识别 + 哈希去重”
- 决策：下载成功后提取格式、分辨率、是否动图、帧数、响应头信息，计算内容哈希并做重复检测。
- 原因：支持后续数据分析、质量评估与存储成本控制；与用户提供的采集脚本策略一致。
- 备选：
  - 仅保存文件路径：实现简单，但无法做可靠去重和格式质量查询。

8. 文件分片能力采用“常规直链优先、Stream API 兜底”
- 决策：图片优先走 `image.data.url` 常规下载；出现大文件、跨设备或流式接口场景时，支持 Stream API 状态驱动处理。
- 原因：保持现有路径简单稳定，同时覆盖分片场景。
- 备选：
  - 全量改成流式：复杂度更高，常规图片场景收益有限。

## Risks / Trade-offs

- [NapCat 连接中断导致事件间断]  
  → Mitigation: 实现 WS 连接生命周期日志、重连监控与心跳事件落库。

- [事件去重困难（message_id 在不同上下文不绝对唯一）]  
  → Mitigation: 保存 `payload_hash`（由原始 payload 计算）并作为幂等辅助键，避免单点依赖 `message_id`。

- [群名与角色字段长度/字符集波动较大]  
  → Mitigation: `group_name`、`sender` 扩展信息只做宽松文本/JSONB 存储，不在首版做严格长度约束。

- [数据库写入引入采集时延]  
  → Mitigation: 采用单条快速写入 + 必要索引，避免同步复杂事务；下载/发布状态分阶段更新。

- [图片 URL 过期导致下载失败]  
  → Mitigation: 明确 URL 过期错误识别和刷新策略，记录刷新尝试与最终状态。

- [大文件或跨设备传输导致单次下载不稳定]  
  → Mitigation: 预留 Stream API 分片状态落库与失败重试路径。

- [新增数据库与管理界面增加运维面]  
  → Mitigation: compose 默认带持久卷、最小暴露端口和环境变量模板，文档明确安全建议（生产禁用默认密码）。

## Migration Plan

1. 新增 NapCat 反向 WS 采集入口与配置项（不立即删除旧 NoneBot 代码）。
2. 新增 PostgreSQL schema 初始化与 repository 层，完成事件/图片/投递三类写入。
3. 将采集链路从 JSONL 为主切换为 PG 为主（必要时保留 JSONL 作为调试副本）。
4. 更新 compose：新增 `db` 与 `pgadmin`，logger 接入数据库并继续连 NATS。
5. 联调验证：私聊文本、私聊图片、群文本、群图片各至少 1 条，核对入库和 NATS 流转。
6. 增补验证：URL 过期/刷新路径、图片格式识别、动图帧数、重复图片去重、流式分片状态记录。

回滚策略：
- 切回旧 `data_logger_service.py` + NoneBot 入口镜像/命令；
- 保留已创建 PG 数据，不影响 processor 现网逻辑。

## Open Questions

- 生产环境是否允许暴露 pgAdmin 端口；若不允许，compose 需要拆分 dev/prod profile。
