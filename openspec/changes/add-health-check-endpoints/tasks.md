## 1. Logger Health Endpoint

- [x] 1.1 在 logger_service aiohttp app 上注册 `GET /health` 路由，handler 返回 HTTP 200 `{"status": "ok"}`（Content-Type: application/json）
- [x] 1.2 在 docker-compose.yml 的 logger 服务中添加 `healthcheck` 块，使用 `python -c "import urllib.request; urllib.request.urlopen('http://localhost:3001/health')"` 探测
- [x] 1.3 编写单元测试：验证 `/health` 返回 200 和预期 JSON body，验证 WebSocket 路由不受影响

## 2. Processor Health Endpoint

- [x] 2.1 新增 processor_service 健康检查 HTTP server 模块（aiohttp TCPSite，port 8080），暴露 `GET /health` → HTTP 200 `{"status": "ok"}`
- [x] 2.2 在 processor_service main 入口中，将 health server 与 NATS tagger worker 通过 `asyncio.gather` 并发运行
- [x] 2.3 在 docker-compose.yml 的 processor 服务中添加 `healthcheck` 块，使用 `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"` 探测
- [x] 2.4 编写单元测试：验证 `/health` 返回 200 和预期 JSON body，验证 health server 不阻塞 NATS worker

## 3. 集成验证

- [x] 3.1 运行全量单元测试，确保无回归
- [x] 3.2 `docker compose up --build -d`，通过 `docker inspect` 确认 logger 和 processor 容器状态为 `healthy`
