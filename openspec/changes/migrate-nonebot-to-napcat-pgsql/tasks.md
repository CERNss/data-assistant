## 1. NapCat Reverse WebSocket Ingestion

- [ ] 1.1 新增 `data-logger` 反向 WebSocket 服务端入口，替换默认 NoneBot 入口
- [ ] 1.2 新增 NapCat 连接配置（监听地址、端口、token、心跳/连接日志）并接入 `.env` 解析
- [ ] 1.3 实现 OneBot11 事件解析器，覆盖 `meta_event`、`message(private/group)` 与 `message_format=array`
- [ ] 1.4 实现图片 URL 提取策略：优先 `message[].data.url`，兜底 `raw_message` CQ 正则
- [ ] 1.5 覆盖 `message_sent`/`notice`/`request` 事件入站并统一进入持久化管线
- [ ] 1.6 增加图片 URL 过期识别与刷新调用链（`nc_get_rkey`/`get_image`/`get_file`/`get_msg`）

## 2. PostgreSQL Persistence Schema And Repositories

- [ ] 2.1 新增 PostgreSQL 连接与启动初始化逻辑（建表/索引幂等执行）
- [ ] 2.2 实现 `onebot_events` 写入（原始 JSONB + 索引字段）
- [ ] 2.3 实现 `onebot_message_images` 写入与下载状态更新（成功/失败）
- [ ] 2.4 实现 `onebot_nats_dispatches` 写入，记录 NATS 发布成功/失败/兜底状态
- [ ] 2.5 为关键查询路径补充索引并验证私聊/群聊样例可检索
- [ ] 2.6 实现图片元数据持久化（sha256、format、width/height、is_animated、frame_count、HTTP 响应头）
- [ ] 2.7 实现去重状态落库（duplicate/saved/failed）与重复文件写入保护
- [ ] 2.8 为流式分片传输补充分阶段状态字段（stream/response/error）及索引

## 3. Keep Existing Image Processor Flow

- [ ] 3.1 将采集侧图片处理改造为“先写库、后下载、再发布 NATS”并保持现有任务载荷兼容
- [ ] 3.2 保持 `data-processor` 侧 NATS 订阅和打标处理逻辑不变
- [ ] 3.3 为失败路径补充审计日志与数据库状态一致性检查

## 4. Containerization And Configuration

- [ ] 4.1 更新 `docker-compose.yml`，新增 PostgreSQL (`db`) 服务与持久卷
- [ ] 4.2 更新 `docker-compose.yml`，新增 pgAdmin 服务与数据库网络联通
- [ ] 4.3 更新 `logger` 服务配置，使其使用 NapCat 反向 WS 模式并连接 PostgreSQL 与 NATS
- [ ] 4.4 更新 `.env.example`/README，补齐 NapCat、PostgreSQL、pgAdmin 运行参数与安全说明
- [ ] 4.5 维护 `data-format.md` 数据契约文档，确保与实现字段和官方协议一致

## 5. Validation

- [ ] 5.1 单元测试补充与修复（配置解析、事件解析、持久化 repository）
- [ ] 5.2 执行 `python -m unittest discover -s tests -p 'test_*.py'` 并修复失败
- [ ] 5.3 执行 `python -m compileall .` 验证语法与导入可用
- [ ] 5.4 联调验证私聊文本/表情/图片与群聊文本/表情/图片全链路落库和 NATS 流转
- [ ] 5.5 验证图片格式识别、动图帧数、哈希去重、URL 过期刷新与分片状态记录
