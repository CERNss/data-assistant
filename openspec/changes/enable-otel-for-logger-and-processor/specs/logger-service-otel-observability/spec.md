## ADDED Requirements

### Requirement: Logger service MUST initialize OpenTelemetry traces and metrics on startup
`logger_service` MUST initialize OpenTelemetry providers for traces and metrics during service startup when OTel is enabled.

#### Scenario: OTel enabled startup
- **WHEN** `OTEL_ENABLED=true` and `logger_service` starts
- **THEN** the service MUST initialize trace and metric providers before processing events

#### Scenario: OTel disabled startup
- **WHEN** `OTEL_ENABLED=false` and `logger_service` starts
- **THEN** the service MUST skip exporter initialization and continue normal runtime behavior

### Requirement: Logger service MUST emit structured JSON logs to stdout
`logger_service` MUST emit application logs as structured JSON lines to stdout for container log collection.

#### Scenario: Structured stdout logging
- **WHEN** logger emits an application log event
- **THEN** the log output MUST be written to stdout in JSON format including stable service metadata fields

#### Scenario: No in-process OTel log exporter requirement
- **WHEN** logger startup configures telemetry
- **THEN** logger MUST NOT require in-process OTel log exporter initialization for log delivery

### Requirement: Logger service MUST emit trace spans for critical pipeline stages
`logger_service` MUST produce trace spans for ingest and dispatch boundaries so operators can reconstruct event lifecycle.

#### Scenario: Message ingest trace
- **WHEN** a OneBot event is received and processed
- **THEN** logger MUST emit spans covering parse, persist, and image-processing stages

#### Scenario: NATS dispatch trace
- **WHEN** logger publishes a tagging task to NATS
- **THEN** logger MUST emit spans indicating publish attempt and publish result status

### Requirement: Logger service MUST expose operational metrics
`logger_service` MUST emit low-cardinality metrics for throughput, failures, and latency of image pipeline operations.

#### Scenario: Download and persistence metrics
- **WHEN** image download or persistence succeeds or fails
- **THEN** logger MUST record counters/histograms that capture outcomes and processing latency

#### Scenario: Publish outcome metrics
- **WHEN** NATS publish succeeds or fails
- **THEN** logger MUST record outcome metrics without using high-cardinality identifiers in metric attributes
