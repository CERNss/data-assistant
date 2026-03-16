## 1. Database Schema

- [x] 1.1 在 `persistence/db.py` 的 `init_db()` 中新增 `onebot_messages` 表 DDL（含所有列和索引）
- [x] 1.2 编写单元测试：验证 `init_db()` 创建 `onebot_messages` 表（可 mock DB 验证 SQL 执行）

## 2. Repository Layer

- [x] 2.1 在 `persistence/repository.py` 新增 `insert_message()` 函数，接收结构化字段并写入 `onebot_messages` 表
- [x] 2.2 新增 `extract_plain_text(segments, raw_message)` 工具函数，从 message_segments 中拼接纯文本，fallback 到 raw_message
- [x] 2.3 新增 `extract_sender_fields(sender)` 工具函数，从 sender dict 提取 nickname、card、role
- [x] 2.4 编写单元测试：验证 `extract_plain_text` 的 segments 拼接、CQ fallback、空输入场景
- [x] 2.5 编写单元测试：验证 `extract_sender_fields` 的正常提取、字段缺失场景

## 3. Pipeline Integration

- [x] 3.1 在 `napcat/pipeline.py` 的 `persist_event()` 中，当 `post_type` 为 `message` 或 `message_sent` 时，调用 `insert_message()` 写入结构化消息
- [x] 3.2 消息写入失败时 logger.error 记录但不中断服务
- [x] 3.3 编写单元测试：验证 group message、private message、message_sent 三种场景写入正确字段
- [x] 3.4 编写单元测试：验证 non-message 事件不触发消息写入
- [x] 3.5 编写单元测试：验证消息写入失败时不影响后续事件处理

## 4. Export CLI

- [x] 4.1 新增 `logger_service/service/export.py`，实现 argparse CLI 入口，支持 --user-id、--group-id、--from、--to、--output、--limit 参数
- [x] 4.2 实现查询逻辑：连接 PostgreSQL，按筛选条件查询 `onebot_messages`，按 event_time 升序排列
- [x] 4.3 实现 JSONL 输出：每行输出一条 JSON 记录到文件或 stdout
- [x] 4.4 编写单元测试：验证参数解析、无筛选条件报错、limit 限制、空结果场景

## 5. Integration Verification

- [x] 5.1 运行全量单元测试，确保无回归
- [x] 5.2 docker compose build 确认镜像构建成功
