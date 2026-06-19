## ADDED Requirements

### Requirement: OTel runtime configuration MUST be consistent across both services
`logger_service` and `processor_service` MUST support the same core OpenTelemetry environment configuration contract.

#### Scenario: Shared core environment keys
- **WHEN** either service loads OTel configuration
- **THEN** it MUST support `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_INSECURE`, and `OTEL_SERVICE_NAME` for traces and metrics

#### Scenario: Service-specific default name
- **WHEN** `OTEL_SERVICE_NAME` is not set
- **THEN** each service MUST apply its own default service name for telemetry resource attributes

### Requirement: Telemetry exporter failures MUST NOT block business startup
Telemetry initialization MUST fail open so observability outages do not stop service runtime.

#### Scenario: Collector unreachable
- **WHEN** OTel exporter initialization or export fails due to endpoint/connectivity error
- **THEN** the service MUST continue startup and log telemetry failure diagnostics for traces/metrics

#### Scenario: Invalid optional telemetry setting
- **WHEN** optional telemetry env input is invalid
- **THEN** the service MUST use safe defaults and continue runtime behavior

### Requirement: Documentation MUST define dual-service OTel setup
Operational documentation MUST describe how to enable and configure OTel for both services.

#### Scenario: Documentation updates
- **WHEN** a developer reads project run/configuration documentation
- **THEN** they MUST see OTel configuration guidance for both `logger_service` and `processor_service`

### Requirement: Logs MUST be forwarded through Fluent Bit from container stdout
Log delivery MUST use container stdout as source and Fluent Bit as the forwarding component to OTLP collector/backend.

#### Scenario: Fluent Bit service in compose
- **WHEN** Docker Compose configuration is inspected for observability setup
- **THEN** it MUST include a Fluent Bit service configured to collect container stdout logs and forward via OTLP

#### Scenario: Fluent Bit health gate
- **WHEN** logger and processor services start under compose
- **THEN** they MUST depend on a healthy Fluent Bit service via `depends_on` with `condition: service_healthy`

#### Scenario: Application log transport boundary
- **WHEN** services emit application logs
- **THEN** logs MUST be emitted to stdout JSON and forwarded by Fluent Bit rather than requiring service-side OTel log exporter wiring

#### Scenario: Docker logging driver forwarding
- **WHEN** compose logging config for logger and processor services is inspected
- **THEN** each service MUST use Docker `logging.driver: fluentd` with `fluentd-address` pointing to `fluent-bit:24224`
