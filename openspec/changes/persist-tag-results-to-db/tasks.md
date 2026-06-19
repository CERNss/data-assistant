## 1. Processor Persistence Module

- [ ] 1.1 新增 `processor_service/service/persistence/config.py`：`PostgresConfig` dataclass + `load_postgres_config()` 函数（仿 logger_service 模式，读 `POSTGRES_DSN` 环境变量）
- [ ] 1.2 新增 `processor_service/service/persistence/db.py`：`DDL_SQL`（含 `chat_image_tags` 表 + 索引）、`init_db()`、`get_pool()`、`close_db()`
- [ ] 1.3 新增 `processor_service/service/persistence/repository.py`：`upsert_tag_result()` 函数（INSERT ON CONFLICT (sha256) DO UPDATE）
- [ ] 1.4 新增 `processor_service/service/persistence/__init__.py`

## 2. Processor Main Integration

- [ ] 2.1 修改 `processor_service/service/main.py`：在 `_main()` 中先调用 `init_db()`，再 `asyncio.gather(health_server, tagger_worker)`
- [ ] 2.2 修改 `docker-compose.yml`：processor 服务添加 `POSTGRES_DSN` 环境变量和 `db: service_started` 依赖
- [ ] 2.3 修改 `.env.example`：添加 processor 相关说明注释

## 3. Tagger Pipeline DB Write

- [ ] 3.1 修改 `tagger_pipeline.py`：标注成功时调用 `upsert_tag_result()` 写入 DB（替代 `_append_tagger_audit()` 成功分支）
- [ ] 3.2 修改 `tagger_pipeline.py`：标注最终失败时调用 `upsert_tag_result()` 写入 DB（替代 `_append_tagger_audit()` 失败分支）
- [ ] 3.3 修改 `tagger_pipeline.py`：移除所有 `_append_tagger_audit()` 调用（保留 retrying 状态的日志输出，但不写 JSONL）
- [ ] 3.4 DB 写入失败时 logger.error 记录，不中断 tagger worker

## 4. Tests

- [ ] 4.1 编写单元测试：验证 `upsert_tag_result()` 的 SQL 参数和 upsert 逻辑
- [ ] 4.2 编写单元测试：验证 processor main 启动时调用 `init_db()`
- [ ] 4.3 编写单元测试：验证 tagger pipeline 标注成功/失败后调用 DB upsert 而非 JSONL 写入
- [ ] 4.4 编写单元测试：验证 DB 写入失败时不中断 tagger worker

## 5. Integration Verification

- [ ] 5.1 运行全量单元测试，确保无回归
- [ ] 5.2 docker compose build 确认镜像构建成功
