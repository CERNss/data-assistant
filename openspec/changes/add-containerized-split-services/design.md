## Context

项目已在代码层将职责拆为 `logger`（采集）与 `processor`（处理），并通过 NATS 传递任务，但当前运行方式仍偏手工，缺少统一的容器化编排标准。该变更需要提供可复用的本地/测试部署拓扑，确保以下关键运行约束被系统性满足：
- `logger` 与 `processor` 独立镜像、独立进程，避免职责回耦。
- `logger` 落盘图片路径与 `processor` 消费路径一致，保证 `image_path` 可访问。
- `nats` 通过服务网络名可被两个业务服务稳定发现。

相关约束：
- 现有代码中任务消息携带的是文件系统路径，不是对象存储 URL。
- 当前消息语义为 core NATS pub/sub（非持久），需要通过启动顺序和文档降低丢失窗口。

## Goals / Non-Goals

**Goals:**
- 定义三服务容器化拓扑：`logger`、`nats`、`processor`。
- 明确 `logger` 与 `processor` 的独立构建与运行入口。
- 明确共享卷与挂载路径规则，保证跨容器路径一致。
- 明确 compose 级网络通信与服务发现规则。
- 提供可执行的启动、回滚与排障路径。

**Non-Goals:**
- 不在本变更中引入 Kubernetes 编排。
- 不改造业务代码为对象存储（S3/OSS）路径模式。
- 不在本变更中实现 JetStream 持久化语义（后续可增量演进）。
- 不改变现有业务插件链路与打标策略。

## Decisions

1. 采用 `docker-compose` 作为首选编排入口
- 决策：新增一个 compose 文件统一管理 `logger`、`nats`、`processor` 三服务。
- 原因：当前阶段目标是快速形成稳定可复现运行环境，compose 成本最低、团队认知门槛低。
- 备选：
  - 分别 `docker run`：参数分散且容易漂移，排障成本高。
  - Kubernetes：能力更强，但引入复杂度与维护成本过高，不符合当前阶段目标。

2. `logger` 与 `processor` 使用两个独立镜像
- 决策：新增 `Dockerfile.logger` 与 `Dockerfile.processor`，分别定义服务入口命令。
- 原因：镜像职责单一，便于独立发布、回滚和资源策略隔离。
- 备选：
  - 单镜像 + 不同 command：可行但职责边界不够明确，版本控制粒度较粗。
  - 单容器混跑多进程：违背服务拆分目标，故障域过大。

3. 使用命名卷并强制同路径挂载（如 `/app/data`）
- 决策：`logger` 与 `processor` 挂载同一命名卷且容器内路径一致。
- 原因：当前消息中 `image_path` 是绝对/规范化文件路径，路径必须在消费端可直接读取。
- 备选：
  - 各自本地卷：路径不共享，消息无法消费。
  - 使用 bind mount 到不同路径：仍可能产生路径失配。
  - 改造为对象存储 URL：架构更优，但超出本次范围。

4. 统一服务网络与 NATS 地址约定
- 决策：三服务置于同一 compose 网络，业务侧 `CHAT_IMAGE_NATS_SERVERS` 使用 `nats://nats:4222`。
- 原因：以服务名作为 DNS 主机名最稳定，避免硬编码宿主机 IP。
- 备选：
  - 使用宿主机地址：跨环境迁移不稳定。
  - 外部共享网络：需要额外治理，当前无必要。

5. 启动顺序约束为 NATS -> processor -> logger
- 决策：文档与 compose 运行说明明确先启动消费者，再启动生产者。
- 原因：在 core NATS pub/sub 下，消费者未就绪窗口可能丢消息。
- 备选：
  - 任意顺序：实现简单但存在明显消息丢失风险。
  - 直接升级 JetStream：可提升可靠性，但超出本次交付边界。

## Risks / Trade-offs

- [消息路径不一致导致处理失败]  
  → Mitigation: 在 compose 中硬性规定共享卷与统一挂载路径，并在文档中标注为不可变约束。

- [core NATS 非持久语义导致早期消息丢失]  
  → Mitigation: 明确启动顺序与健康检查建议；后续规划 JetStream 作为增强项。

- [双镜像维护成本增加]  
  → Mitigation: 抽取公共构建层（基础依赖、代码拷贝流程）并保持 Dockerfile 结构一致。

- [环境变量配置漂移]  
  → Mitigation: 提供 `.env.example` 作为唯一参考，compose 统一读取并在 README 中维护变量清单。

- [共享卷历史数据膨胀]  
  → Mitigation: 增加运维清理指引（按目录/时间策略清理），并将卷生命周期纳入发布检查项。

## Migration Plan

1. 在 `develop` 引入 compose 与双 Dockerfile（不改动 `main` 发布策略）。
2. 补齐 `.env.example`，写入 NATS 地址、服务开关和路径约束。
3. 本地执行 `docker compose up` 做联调，确认 `logger -> nats -> processor` 主链路可用。
4. 通过日志与审计文件验证消息流转和图片路径可读性。
5. 形成发布说明，后续通过 `develop -> main` 合并发版。

回滚策略：
- 回退到上一个 compose 与镜像版本；
- 如需紧急恢复，可切回已有的本机进程启动方式（`python data_logger_service.py` / `python data_processor_service.py`）。

## Open Questions

- 是否在下一阶段引入 JetStream durable consumer 以增强消息可靠性？
- 生产环境是继续共享本地卷，还是迁移到对象存储并传递对象地址？
- 是否需要在 compose 中增加 `healthcheck` 与启动依赖条件，减少冷启动窗口失败率？
