## Context

logger_service 已有 `onebot_events` 表存储所有 OneBot11 事件的完整 raw JSON，并通过 `onebot_message_images` 表单独追踪图片下载状态。事件持久化流程在 `napcat/pipeline.py` 的 `persist_event()` 中完成，通过 `persistence/repository.py` 的 `insert_event()` 写入 DB。

当前的 `onebot_events` 表虽然有 `user_id`、`group_id` 索引，但缺少发送者昵称/群名片等结构化字段，消息纯文本需要从 JSONB 中拼接提取，不利于按人/按群检索和导出。

`OneBotEvent` dataclass 中已解析出 `sender` dict（含 `user_id`、`nickname`、`card`、`role`）和 `message_segments` 列表，只需在持久化时额外提取写入新表。

## Goals / Non-Goals

**Goals:**
- 从 `post_type=message` 和 `post_type=message_sent` 事件中提取结构化字段，写入专用 `onebot_messages` 表
- 支持按 `user_id`、`group_id`、时间范围高效查询
- 提供 CLI 导出工具，输出 JSONL 格式

**Non-Goals:**
- 不替代 `onebot_events` 表（它继续存储所有事件类型的完整 raw JSON，作为审计日志）
- 不做全文搜索（如果未来需要，可加 GIN 索引，但本次不做）
- 不做消息的实时推送或 API 查询接口
- 不处理 notice / request / meta_event 类型

## Decisions

### 1. 新表 `onebot_messages` 关联 `onebot_events`，而非独立存储

`onebot_messages.event_id` FK 引用 `onebot_events.id`。好处：
- 避免重复存储 raw JSON（通过 JOIN 仍可取到完整原始数据）
- `onebot_events` 继续作为不可变审计日志
- 删除事件时消息记录级联清理

**备选方案**：独立表，不建 FK。  
**否决原因**：失去数据一致性保证，且 event_id 关联在图片表中已有先例。

### 2. `plain_text` 字段：在写入时从 segments 拼接，而非查询时计算

从 `message_segments` 中提取所有 `type=text` 的 `data.text` 拼接为 `plain_text` 字段。写入时一次性计算，查询时零开销。

**备选方案**：存 segments JSONB，查询时用 `jsonb_array_elements` 提取。  
**否决原因**：导出时每行都要做 JSON 计算，性能差且 SQL 复杂。

### 3. 同时存 `plain_text` 和 `message_segments` JSONB

`plain_text` 用于快速查看/导出，`message_segments` 保留完整结构（含图片、表情、at 等非文本段），未来可用于消息重建。

### 4. sender 字段提取为独立列

从 `event.sender` dict 中提取 `nickname`、`card`（群名片）、`role` 为独立列。理由：
- 按发送者昵称/名片搜索是常见需求
- 群名片随时间变化，记录当时的值有历史价值

### 5. 导出 CLI 用独立脚本，不嵌入服务主进程

CLI 直连 PostgreSQL 读取，通过 `python3 -m logger_service.service.export` 运行。不需要 logger_service 运行中。

**备选方案**：HTTP API 端点。  
**否决原因**：当前没有 REST API 层，为导出功能新增 API server 过度设计。CLI 足够直接。

### 6. 导出格式：JSONL

每行一条 JSON 记录，便于流式处理、grep 过滤、导入其他系统。

**备选方案**：CSV。  
**否决原因**：消息内容可能含逗号、换行、emoji 等，CSV 转义复杂且易出错。

## Risks / Trade-offs

- **写入开销翻倍**：每条消息从 1 次 INSERT 变为 2 次（events + messages）。→ 对于聊天消息频率（远低于数据库 TPS 上限）影响可忽略。两次 INSERT 在同一事务中执行。
- **plain_text 与 segments 不一致**：如果只有 CQ 格式字符串（无 array segments），`plain_text` 回退为 `raw_message`。→ 可接受，CQ 格式的 raw_message 已经是人类可读的。
- **schema 迁移**：已运行的实例需要执行新的 DDL。→ `init_db()` 使用 `CREATE TABLE IF NOT EXISTS`，新增表不影响已有数据。

## Migration Plan

1. 部署新代码后，`init_db()` 自动创建 `onebot_messages` 表
2. 新消息自动写入新表；历史消息不回填（如需回填，可后续写一次性脚本从 `onebot_events.raw` 提取）
3. 回滚：删除新代码中的写入逻辑，新表保留不影响运行
