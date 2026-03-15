## ADDED Requirements

### Requirement: Processor exposes HTTP health endpoint
processor_service SHALL expose `GET /health` on a dedicated lightweight HTTP server (default port 8080).
The endpoint SHALL return HTTP 200 with JSON body `{"status": "ok"}` whenever the aiohttp event loop is running and able to handle requests.
No external dependency (NATS, fluent-bit) SHALL be checked.
The health server SHALL run concurrently with the NATS tagger worker without blocking it.

#### Scenario: Health check returns 200 when service is running
- **WHEN** a GET request is sent to `http://localhost:8080/health`
- **THEN** the response status is 200
- **THEN** the response body is `{"status": "ok"}`
- **THEN** the `Content-Type` header is `application/json`

#### Scenario: Docker healthcheck passes when service is running
- **WHEN** Docker executes the healthcheck command inside the container
- **THEN** the command exits with code 0
- **THEN** Docker marks the container status as `healthy`

#### Scenario: Health server does not block NATS worker
- **WHEN** the health server is running
- **THEN** the NATS tagger worker continues to consume and process messages normally

#### Scenario: Health server starts with the service
- **WHEN** processor_service main entry point starts
- **THEN** the health HTTP server is started before or concurrently with the NATS worker
- **THEN** both run until the process is terminated
