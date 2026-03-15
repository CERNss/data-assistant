## Why

logger_service 和 processor_service 没有健康检查端点，Docker 无法感知它们的运行状态。
同时 docker-compose.yml 中两者已经依赖 fluent-bit 的 `service_healthy`，补全自身健康检查能让整个服务编排形成完整闭环，并为后续监控和容器编排平台集成打好基础。

## What Changes

- **logger_service**：在现有 aiohttp HTTP server（port 3001）上新增 `GET /health` 路由，返回 `{"status": "ok"}`，HTTP 200。
- **processor_service**：新增一个轻量 aiohttp HTTP server（port 8080），仅暴露 `GET /health` 路由，返回同样的 `{"status": "ok"}`，HTTP 200。
- **docker-compose.yml**：为 logger 和 processor 服务各添加 `healthcheck` 块，使用 `curl -f http://localhost:<port>/health` 探测。
- **depends_on 不变**：nats、db、fluent-bit 三者并行启动，互不等待；logger 和 processor 继续等待 `fluent-bit: service_healthy`、`nats: service_started`、`db: service_started`（logger 专属）全部满足后才启动。

## Capabilities

### New Capabilities

- `logger-health-endpoint`: logger_service 的 HTTP 健康检查端点，挂载在现有 aiohttp app 上，供 Docker healthcheck 及外部监控探测。
- `processor-health-endpoint`: processor_service 的 HTTP 健康检查端点，独立轻量 HTTP server，供 Docker healthcheck 及外部监控探测。

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- **logger_service/service/napcat/connection.py**（或同级路由注册处）：新增 `/health` 路由。
- **processor_service/service/main.py**（或新增 `health.py`）：新增独立 aiohttp TCPSite，监听 port 8080。
- **docker-compose.yml**：logger 和 processor 服务各加 `healthcheck` 块；processor 服务新增 port 8080 暴露（可选，仅 healthcheck 用途时不必对外暴露）。
- **无新依赖**：aiohttp 已在 requirements.txt 中，无需引入额外包。
