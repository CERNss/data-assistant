## 1. 实现

- [x] 1.1 新增 `bot.py` 作为启动入口并注册 QQ 适配器
- [x] 1.2 新增 `plugins/group_logger.py` 记录群消息和群通知
- [x] 1.3 更新 `pyproject.toml`，启用 `plugins` 目录
- [x] 1.4 更新 `README.md`，补充配置和运行说明

## 2. 验证

- [x] 2.1 通过 `python -m py_compile bot.py plugins/group_logger.py`
- [ ] 2.2 在真实 QQ 机器人凭据下运行 `nb run` 并确认 `data/*.jsonl` 持续写入
