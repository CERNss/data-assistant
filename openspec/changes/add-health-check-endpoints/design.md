## Context

logger_service 已有一个 aiohttp HTTP server（port 3001），仅暴露 WebSocket 路由。
processor_service 是纯 NATS 消费者，没有任何 HTTP server。
两者均运行在 `python:3.11-slim` 镜像中，该镜像不预装 curl/wget。
健康检查的目的是：进程在线、事件循环正常响应，不验证任何外部依赖。

## Goals / Non-Goals

**Goals:**
- logger 和 processor 各提供 `GET /health` → HTTP 200 `{"status": "ok"}`
- docker-compose 中两个服务加上 `healthcheck` 块，使 Docker 能感知其就绪状态
- 不修改现有 `depends_on` 结构

**Non-Goals:**
- 不做深度检查（不探测 PostgreSQL、NATS、fluent-bit 连通性）
- 不做 liveness/readiness 区分（当前规模不需要）
- 不对外暴露 processor 的健康端口（docker-compose healthcheck 在容器内部访问即可）
- 不修改 Dockerfile（不安装 curl/wget）

## Decisions

### 1. logger：复用现有 aiohttp app，而非新开 server

logger 已有 aiohttp `web.Application` 在 port 3001 上运行。直接在该 app 上注册 `/health` 路由即可，零额外资源开销。

**备选方案**：新开一个独立 HTTP server（如 port 8080）。  
**否决原因**：引入额外端口和 TCPSite 生命周期管理，复杂度与收益不成比例。

### 2. processor：新增独立轻量 aiohttp TCPSite（port 8080）

processor 无任何 HTTP server，需从零引入。选择 aiohttp（已在 requirements.txt 中）在独立端口起一个最小 TCPSite，与 NATS worker 协程并发运行（`asyncio.gather`）。

**备选方案 A**：TCP socket 存活探测（docker healthcheck 直接检测端口连通性）。  
**否决原因**：TCP 存活不等于进程健康，无法区分端口被占用和服务正常响应的情况。

**备选方案 B**：Unix signal handler 写状态文件，healthcheck 读文件。  
**否决原因**：实现繁琐，不如 HTTP 统一且可扩展。

### 3. Healthcheck 命令：用 Python 内置 urllib，不安装 curl

`python:3.11-slim` 不含 curl/wget，安装会增加镜像层和体积。Python 本身即可完成 HTTP 探测：

```
python -c "import urllib.request; urllib.request.urlopen('http://localhost:<port>/health')"
```

**备选方案**：在 Dockerfile 中 `RUN apt-get install -y curl`。  
**否决原因**：不必要地扩大镜像体积，增加安全攻击面。

### 4. 响应格式：JSON `{"status": "ok"}`

简单、可扩展（未来可加字段），与常见健康检查规范兼容。HTTP 状态码 200 是唯一有效值。

## Risks / Trade-offs

- **浅检查的局限**：进程活着但 NATS/DB 断连时，healthcheck 仍返回 healthy。这是已知取舍，符合当前设计目标（不做深度检查）。如未来需要深度检查，可扩展响应体而不破坏接口。
- **processor port 8080 冲突**：若宿主机或其他容器已占用 8080，需调整。当前 compose 未对外 expose 该端口，仅容器内部使用，冲突风险极低。

## Migration Plan

1. 代码变更：logger 加路由，processor 加 health server
2. docker-compose 加 healthcheck 块
3. `docker compose up --build -d` 重建两个服务镜像
4. 验证：`docker inspect <container> | grep -A5 Health`

回滚：移除代码改动和 compose healthcheck 块，`docker compose up --build -d` 即可。
