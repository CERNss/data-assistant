## Why

当前服务虽然已在代码层拆分为 `logger` 与 `processor`，但缺少标准化容器编排与部署约束，导致环境搭建、联调和发布流程不稳定。需要引入统一的容器化运行方式，把服务边界、网络和共享存储关系固定下来，支撑后续在 `develop` 持续迭代并在 `main` 稳定发版。

## What Changes

- 新增基于 Docker Compose 的三服务编排：`logger`、`nats`、`processor`。
- 新增两个独立构建镜像：
  - `logger` 镜像只运行采集服务入口。
  - `processor` 镜像只运行处理服务入口。
- 约束 `logger` 与 `processor` 使用同一个共享卷并挂载到同一路径，确保 NATS 消息中的 `image_path` 在处理侧可访问。
- 约束三服务在同一编排网络中通信，并统一 NATS 服务发现方式（通过服务名连接）。
- 补充部署文档与环境变量示例，明确启动顺序、运行前提与常见风险（如非持久消息模式下的丢失窗口）。

## Capabilities

### New Capabilities
- `containerized-split-services`: 定义 `logger`、`nats`、`processor` 的容器化拓扑、共享卷约束、网络连通与运行启动要求。
- `service-specific-images`: 定义 `logger` 与 `processor` 的独立镜像构建与运行入口约束，避免单容器混跑。

### Modified Capabilities
- (none)

## Impact

- Affected code/config:
  - `docker-compose.yml`（新增）
  - `Dockerfile.logger`（新增）
  - `Dockerfile.processor`（新增）
  - 运行配置与示例环境变量文件（新增或更新）
  - `README.md`（更新容器化部署说明）
- Runtime dependencies:
  - Docker / Docker Compose
  - NATS 官方镜像（建议启用 JetStream 以便后续增强可靠性）
- Operational impact:
  - 开发与测试将从“本机手工进程启动”迁移为“编排统一启动”
  - 部署时需要管理共享数据卷生命周期与镜像版本
