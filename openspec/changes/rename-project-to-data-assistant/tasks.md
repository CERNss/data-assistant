## 1. Naming Update

- [x] 1.1 将项目元数据名称更新为 `data-assistant`
- [x] 1.2 更新默认运行命名（OTEL service name、NATS client name）

## 2. Service Entrypoints

- [x] 2.1 为采集服务新增顶层入口脚本
- [x] 2.2 为处理服务新增顶层入口脚本
- [x] 2.3 调整 `bot.py` 以提供显式 `main()` 入口

## 3. Docs And Verification

- [x] 3.1 更新 README 启动与配置说明
- [x] 3.2 更新测试断言覆盖默认命名变更
- [x] 3.3 通过 `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
