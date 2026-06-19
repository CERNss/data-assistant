## Context

项目目前为 NoneBot2 初始化工程，尚无业务插件。  
群消息采集的最小落地方式是基于事件订阅，在事件到达时直接写入 JSONL。

## Goals

- 无侵入地接入现有 NoneBot 启动流程。
- 记录可追溯的结构化事件数据，便于后续消费。
- 保持实现简单，先满足可运行与可验证。

## Non-Goals

- 不实现历史消息回溯（平台不支持）。
- 不实现复杂存储（数据库/消息队列）和数据清洗。
- 不在本次变更中实现权限管理和脱敏。

## Architecture

- 启动层：`bot.py` 负责 `nonebot.init()`、注册 `QQAdapter`、加载 `plugins`。
- 插件层：`plugins/group_logger.py` 使用 `on_type(...)` 订阅：
  - `GroupAtMessageCreateEvent`
  - `GroupMsgReceiveEvent`
  - `GroupMsgRejectEvent`
- 存储层：按事件类型写入：
  - `data/group_messages.jsonl`
  - `data/group_notices.jsonl`

## Data Model

每条记录包含：

- `logged_at`：本地记录时间（UTC ISO8601）
- `event_name` / `event_description`
- 标识字段（群、用户、消息 ID）
- `raw_event`：事件原始结构（`model_dump(mode="json")`）

## Tradeoffs

- JSONL 优点是实现快、可直接 grep/流式处理；缺点是缺少强约束和索引能力。
- 使用 `GroupAtMessageCreateEvent` 可快速拿到群消息，但依赖平台事件策略，是否覆盖“所有群消息”由平台权限决定。
