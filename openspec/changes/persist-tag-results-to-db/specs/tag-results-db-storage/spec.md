## ADDED Requirements

### Requirement: chat_image_tags table schema
系统 SHALL 在 processor_service 的 `init_db()` 中创建 `chat_image_tags` 表，包含以下列：
- `id` bigserial PRIMARY KEY
- `sha256` text NOT NULL UNIQUE（图片文件内容 hash，天然去重键）
- `image_id` bigint NOT NULL（最近一次关联的 image_id）
- `tags` jsonb NOT NULL DEFAULT '[]'（标签字符串数组）
- `tag_count` int NOT NULL DEFAULT 0
- `status` text NOT NULL（'success' / 'failed'）
- `error` text（失败时的错误信息）
- `attempt_count` int NOT NULL DEFAULT 1
- `image_path` text（图片文件路径）
- `context` jsonb（chat_type、chat_id、message_id 等来源信息）
- `tagged_at` timestamptz NOT NULL DEFAULT now()

系统 SHALL 创建以下索引：
- `idx_chat_image_tags_sha256` ON (sha256)
- `idx_chat_image_tags_status` ON (status)
- `idx_chat_image_tags_tagged_at` ON (tagged_at)

#### Scenario: Table created on processor init_db
- **WHEN** processor_service 启动并调用 `init_db()`
- **THEN** `chat_image_tags` 表被创建（IF NOT EXISTS）

#### Scenario: Duplicate sha256 rejected
- **WHEN** 插入两条 sha256 相同的记录
- **THEN** 第二次插入触发 UNIQUE 冲突

### Requirement: Upsert tag results on tagger completion
当 tagger 完成标注后，系统 SHALL 将结果通过 upsert 写入 `chat_image_tags` 表。

Upsert 规则：
- INSERT ON CONFLICT (sha256) DO UPDATE
- 更新 tags、tag_count、status、attempt_count、image_id、image_path、context、tagged_at

#### Scenario: First successful tag for an image
- **WHEN** sha256 为 "abc123" 的图片首次被成功标注，结果为 ["cat", "outdoor"]
- **THEN** `chat_image_tags` 新增一行：sha256="abc123", tags=["cat","outdoor"], tag_count=2, status="success"

#### Scenario: Same image tagged again (dedup)
- **WHEN** sha256 为 "abc123" 的图片再次被标注（来自不同消息）
- **THEN** 已有行被更新（tags/tagged_at 刷新），不新增行

#### Scenario: Tag failure recorded
- **WHEN** 标注失败且 sha256 无已有成功记录
- **THEN** 写入 status="failed", error 非空

#### Scenario: DB write failure does not crash processor
- **WHEN** DB 写入失败（连接异常等）
- **THEN** 错误通过 logger.error 记录
- **THEN** tagger worker 继续处理后续任务

### Requirement: Processor connects to PostgreSQL
processor_service SHALL 在启动时通过 `POSTGRES_DSN` 环境变量连接 PostgreSQL，初始化连接池。

#### Scenario: Processor starts with DB connection
- **WHEN** processor_service 的 main 启动
- **THEN** DB pool 初始化完成后，health server 和 tagger worker 才开始运行

#### Scenario: Processor depends on db service in compose
- **WHEN** docker-compose up processor
- **THEN** processor 等待 db 服务启动后才启动

## MODIFIED Requirements

### Requirement: Remove JSONL audit log from tagger pipeline
tagger_pipeline.py 中的 `_append_tagger_audit()` 调用 SHALL 被移除，改为 DB upsert 调用。
`audit.py` 中的 `append_json_line` 函数保留不删（logger_service 仍在使用）。

#### Scenario: No JSONL written after tag completion
- **WHEN** tagger 完成标注（成功或失败）
- **THEN** 不向 `group_image_tags.jsonl` 写入任何内容
- **THEN** 结果写入 `chat_image_tags` DB 表
