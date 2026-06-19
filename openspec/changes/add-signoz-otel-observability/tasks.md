## 1. 实现

- [x] 1.1 新增 `telemetry.py`，实现 OTel trace/log 初始化
- [x] 1.2 更新 `bot.py` 在启动时初始化 telemetry
- [x] 1.3 更新 `plugins/group_logger.py` 增加关键 span 和错误标记
- [x] 1.4 更新 `pyproject.toml` 增加 OTel 依赖
- [x] 1.5 更新 `README.md` 增加 Signoz 接入配置示例
- [x] 1.6 增加未捕获异常采集与 loguru 日志桥接

## 2. 验证

- [x] 2.1 通过 `python -m py_compile bot.py plugins/group_logger.py telemetry.py`
- [ ] 2.2 本地启动后确认 OTel 初始化日志正常，且无配置时可安全降级
