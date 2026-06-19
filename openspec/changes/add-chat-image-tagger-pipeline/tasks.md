## 1. Pipeline Integration

- [x] 1.1 扩展 `chat_image` 配置，新增打标流水线开关、路径、批处理、超时与重试参数
- [x] 1.2 在图片保存成功后入队打标任务，保证“先收集、后打标”执行顺序
- [x] 1.3 新增打标流水线模块，支持队列读写、批处理执行、失败重试与审计日志
- [x] 1.4 新增手动打标 CLI，用于离线/定时消费队列

## 2. Documentation And Testing

- [x] 2.1 更新 `README.md`，补充外部组件集成方式、环境变量与运行命令
- [x] 2.2 增加配置测试，覆盖默认值与环境变量覆盖行为
- [x] 2.3 增加流水线测试，覆盖去重入队、成功消费、失败重试到最终失败
- [x] 2.4 通过 `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`

## 3. Runtime Validation

- [ ] 3.1 在真实 `Eagle_AItagger_byWD1.4` + 模型环境中执行端到端验证，确认标签审计输出与质量
