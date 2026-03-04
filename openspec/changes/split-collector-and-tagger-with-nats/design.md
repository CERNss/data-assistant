## Context

现有系统已具备图片采集与打标能力，但打标逻辑仍可被采集进程直接触发。目标是将职责拆分为两个微服务：
- 采集服务（Collector）：接收 QQ 事件、下载原图、发布打标任务。
- 打标服务（Tagger Worker）：订阅任务、执行打标流水线、写入打标审计。

消息中间件采用 NATS，以实现异步解耦和独立部署。

## Goals / Non-Goals

**Goals:**
- 明确分离采集与打标运行进程。
- 采集侧仅做 NATS 发布，避免打标耗时影响在线处理。
- 打标侧通过 NATS 消费并复用现有队列+重试能力。
- 支持开关和降级配置，便于灰度切换。

**Non-Goals:**
- 不在本变更中引入复杂分布式调度（如 Celery/Kafka）。
- 不改造外部打标工具内部实现。
- 不实现跨服务事务一致性。
- 不在本变更中实现持久化消息投递语义（当前为 core NATS at-most-once）。

## Decisions

1. NATS 作为服务间通信总线
- 使用 `nats-py`，采集服务 publish 到固定 subject，打标服务 subscribe 消费。
- 备选：
  - HTTP 回调：耦合高、削峰能力差。
  - Redis Stream/Kafka：部署复杂度更高。

2. 采集服务默认“发布优先，本地执行关闭”
- 图片落盘成功后构造标准消息并发布 NATS；若未启用 NATS，则可回落到原本本地入队行为。
- 这样支持逐步迁移，不强制一次性切换。

3. 打标服务复用现有 `tagger_pipeline`
- NATS 消息进入后先入本地队列，再按现有批处理、重试与审计执行。
- 备选直接“收到一条执行一条”被放弃，因为会削弱当前批处理效率与重试策略。

4. 增加独立服务入口脚本
- 新增 worker 入口（非 nonebot 进程），负责连接 NATS、订阅、驱动 tagger queue。
- 采集服务继续使用现有 `bot.py` 启动。

## Risks / Trade-offs

- [NATS 不可用] 采集侧任务投递失败  
  → Mitigation: 记录错误日志并可配置回退到本地队列。

- [重复消息] 上层重试或重复发布时可能重复消费  
  → Mitigation: 保持基于 `image_path` 的队列去重逻辑。

- [消息丢失] core NATS 在无订阅者或网络异常窗口下可能丢失消息  
  → Mitigation: 运维上先启动 worker 后启动 collector；后续可升级到 JetStream durable consumer。

- [消费者崩溃] 消费中断导致积压  
  → Mitigation: 使用 queue group + 持续运行 worker，并保留本地队列重试。

- [配置复杂度上升] 运维成本增加  
  → Mitigation: 提供最小必需配置与默认值，README 给出两服务启动方式。

## Migration Plan

1. 部署代码并配置 NATS 地址。
2. 启动打标服务（NATS worker）。
3. 在采集服务开启 NATS 发布开关。
4. 观察 `group_images.jsonl` 与 `group_image_tags.jsonl`，确认端到端链路正常。
5. 稳定后关闭采集侧本地自动打标（如果此前启用）。

回滚：
- 关闭 NATS 发布开关，恢复本地队列模式即可。

## Open Questions

- 是否需要 NATS JetStream 持久化以降低消息丢失风险？
- 是否需要按群聊维度分 subject 以便隔离流量？
