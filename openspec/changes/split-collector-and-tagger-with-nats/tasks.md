## 1. NATS Integration

- [x] 1.1 在配置层新增 NATS 连接、subject、queue group、发布开关配置
- [x] 1.2 新增 NATS 客户端模块，支持采集侧发布与打标侧订阅
- [x] 1.3 更新依赖清单，加入 `nats-py`

## 2. Service Split

- [x] 2.1 改造采集服务：图片保存成功后发布 NATS 打标任务
- [x] 2.2 新增独立打标 worker 入口，订阅 NATS 并驱动打标流水线
- [x] 2.3 保持本地队列与重试机制，确保消费幂等和失败可恢复

## 3. Validation And Docs

- [x] 3.1 增加测试覆盖 NATS 消息封装/消费与配置行为
- [x] 3.2 更新 README，给出两个微服务的启动方法与环境变量示例
- [x] 3.3 通过 `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
