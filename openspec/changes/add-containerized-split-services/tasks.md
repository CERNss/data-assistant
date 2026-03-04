## 1. Compose Topology And Runtime Wiring

- [x] 1.1 新增 `docker-compose.yml`，定义 `logger`、`nats`、`processor` 三个服务
- [x] 1.2 为 `nats` 服务配置官方镜像与基础运行参数（包含对 4222 端口的服务能力）
- [x] 1.3 为 `logger` 与 `processor` 配置同一个命名卷，并挂载到相同容器路径（例如 `/app/data`）
- [x] 1.4 为三服务配置统一网络与服务发现，确保业务侧通过 `nats://nats:4222` 连接 NATS
- [x] 1.5 在 compose 运行说明中明确启动顺序为 `nats -> processor -> logger`

## 2. Service-Specific Image Build

- [x] 2.1 新增 `Dockerfile.logger`，仅启动采集服务入口（`data_logger_service.py` 或等价入口）
- [x] 2.2 新增 `Dockerfile.processor`，仅启动处理服务入口（`data_processor_service.py` 或等价入口）
- [x] 2.3 配置 compose 使用对应 Dockerfile 分别构建 `logger` 与 `processor` 镜像
- [x] 2.4 校验任一服务容器内不存在“采集+处理”混跑进程

## 3. Configuration And Documentation

- [x] 3.1 新增或更新 `.env.example`，补充容器化运行所需环境变量（NATS 地址、服务开关、共享路径约束）
- [x] 3.2 更新 `README.md` 的容器化部署章节，说明双镜像策略、同卷同路径约束与网络约束
- [x] 3.3 在文档中明确 core NATS 非持久语义风险与后续 JetStream 增强方向

## 4. Validation

- [ ] 4.1 通过 `docker compose up` 验证三服务可正常启动并互通
- [ ] 4.2 发送一条包含图片的采集链路事件，验证 `logger -> nats -> processor` 端到端流转
- [ ] 4.3 验证 `processor` 能读取 `logger` 落盘路径（覆盖共享卷路径一致性）
- [x] 4.4 记录验证结果与故障排查要点，补充到变更文档或 README

说明：4.1-4.3 保留为流水线或真实环境联调任务，不在本次本地实现完整性检查中完成。
