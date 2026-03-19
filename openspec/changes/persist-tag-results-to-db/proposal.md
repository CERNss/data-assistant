## Why

图片标注结果目前只写入 JSONL audit log 文件（`group_image_tags.jsonl`），无法结构化查询，也无法与图片元数据关联。同一张图片被多次发送时，tagger 会重复标注并追加多行记录，造成冗余。

需要将标注结果持久化到 PostgreSQL，以 `sha256` 为唯一键做天然去重——同一张图片内容无论被发多少次，标注结果只存一行。同时移除 JSONL audit log，DB 作为唯一存储。

## What Changes

- processor_service 新增 PostgreSQL 连接能力（连接与 logger_service 相同的 DB 实例）
- 新增 `chat_image_tags` 表，以 `sha256` 为 UNIQUE 约束
- 修改 `tagger_pipeline.py`，标注成功/失败后写入 DB（upsert），替代 JSONL 写入
- 移除 `audit.py` 的 JSONL 写入逻辑和相关配置
- docker-compose 中为 processor 添加 `POSTGRES_DSN` 环境变量

## Capabilities

### New Capabilities

- `tag-results-db-storage`: 将图片标注结果（tags、status、attempt_count 等）持久化到 `chat_image_tags` 表，sha256 天然去重。

### Modified Capabilities

- `tagger-pipeline`: 移除 JSONL audit log 写入，改为 DB 写入。

## Impact

- **processor_service/service/persistence/**：新增 DB 连接和 repository 模块（仿 logger_service 模式）
- **processor_service/service/chat_image/tagger_pipeline.py**：替换 `_append_tagger_audit()` 为 DB upsert 调用
- **processor_service/service/chat_image/audit.py**：移除或清空
- **processor_service/service/main.py**：启动时初始化 DB 连接池
- **docker-compose.yml**：processor 服务添加 `POSTGRES_DSN` 环境变量
- **无新依赖**：asyncpg 已在 requirements.txt 中
