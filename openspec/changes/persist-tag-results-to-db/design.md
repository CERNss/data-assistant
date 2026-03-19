## Context

processor_service 当前无 PostgreSQL 连接，标注结果写入 JSONL 文件。logger_service 已建立了完善的 DB 模块（`persistence/db.py` + `persistence/repository.py`），可作为参考模式。

两个服务共享同一个 PostgreSQL 实例（`docker-compose.yml` 中的 `db` 服务），processor 只需配置相同的 `POSTGRES_DSN` 即可连接。

Eagle_AItagger 输出格式为 `metadata.json`，仅含 `tags: string[]`，无置信度分数。

## Goals / Non-Goals

**Goals:**
- processor_service 连接 PostgreSQL，标注结果写入 `chat_image_tags` 表
- `sha256` 作为 UNIQUE 约束，同一图片内容只存一行标注结果
- 标注成功时 upsert（INSERT ON CONFLICT UPDATE），确保重复标注时更新而非报错
- 完全移除 JSONL audit log 写入
- processor main 启动时初始化 DB pool

**Non-Goals:**
- 不从 logger_service 迁移 DB 模块代码（processor 有自己的 persistence 模块）
- 不回填历史 JSONL 数据到 DB
- 不修改 logger_service 的代码
- 不做标注结果的查询 API

## Decisions

### 1. processor_service 新建独立的 persistence 模块

在 `processor_service/service/persistence/` 下新建 `config.py`、`db.py`、`repository.py`，结构与 logger_service 相同但独立。

**备选方案**：共享 logger_service 的 persistence 模块。  
**否决原因**：两个服务是独立部署单元，共享会引入部署耦合。

### 2. `sha256` 作为 UNIQUE 约束，而非 `image_id`

同一张图片被多次发送会产生不同的 `image_id`，但 `sha256` 相同。以 `sha256` 去重符合「同图片内容 = 同标注结果」的语义。

**备选方案**：`image_id` UNIQUE。  
**否决原因**：无法跨消息去重，同一图片内容会存多行。

### 3. Upsert 策略：ON CONFLICT (sha256) DO UPDATE

标注成功时：更新 tags、tag_count、status、attempt_count、tagged_at。  
标注失败时：仅在无成功记录时写入（不覆盖已成功的结果）。

### 4. 表中保留 image_id 和 context 字段

虽然 sha256 是主去重键，但保留 `image_id`（最近一次标注关联的 image_id）和 `context` JSONB（chat_type、chat_id 等）便于追溯来源。

### 5. 移除 audit.py 中的 JSONL 写入

`_append_tagger_audit()` 调用全部替换为 DB upsert。`audit.py` 中的 `append_json_line` 函数保留（logger_service 的 pipeline.py 也在用它），但 processor 的 tagger 流程不再调用。

### 6. DB pool 在 processor main 中与 health server 和 tagger worker 并发启动

`_main()` 中先 `init_db()`，再 `asyncio.gather(health_server, tagger_worker)`。

## Risks / Trade-offs

- **首次标注 sha256 可能来自不同 image_id**：context 中的 chat_id/message_id 只反映最近一次关联，不影响标注结果正确性。
- **processor 需要等 DB 就绪**：docker-compose 中 processor 需新增 `db: service_started` 依赖。
- **移除 JSONL 后无文件级备份**：DB 是唯一存储。可接受——PostgreSQL 有自己的备份机制。

## Migration Plan

1. processor_service 新增 persistence 模块 + DB 初始化
2. docker-compose 为 processor 添加 `POSTGRES_DSN` 和 `db` 依赖
3. tagger_pipeline 替换 audit 写入为 DB upsert
4. 移除 tagger 相关的 JSONL audit 调用
5. 部署后新标注结果自动进 DB；历史 JSONL 数据保留但不再追加
6. 回滚：恢复 audit 写入代码，移除 DB 写入
