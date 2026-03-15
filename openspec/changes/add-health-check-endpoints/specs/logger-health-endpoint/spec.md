## ADDED Requirements

### Requirement: Logger exposes HTTP health endpoint
logger_service SHALL expose `GET /health` on the same port as the WebSocket server (default 3001).
The endpoint SHALL return HTTP 200 with JSON body `{"status": "ok"}` whenever the aiohttp event loop is running and able to handle requests.
No external dependency (PostgreSQL, NATS, fluent-bit) SHALL be checked.

#### Scenario: Health check returns 200 when service is running
- **WHEN** a GET request is sent to `http://localhost:3001/health`
- **THEN** the response status is 200
- **THEN** the response body is `{"status": "ok"}`
- **THEN** the `Content-Type` header is `application/json`

#### Scenario: Docker healthcheck passes when service is running
- **WHEN** Docker executes the healthcheck command inside the container
- **THEN** the command exits with code 0
- **THEN** Docker marks the container status as `healthy`

#### Scenario: Health endpoint does not affect WebSocket route
- **WHEN** the `/health` route is registered on the aiohttp app
- **THEN** the existing WebSocket route at `/onebot/v11/ws` continues to function normally
