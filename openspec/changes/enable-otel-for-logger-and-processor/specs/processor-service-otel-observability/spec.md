## ADDED Requirements

### Requirement: Processor service MUST initialize OpenTelemetry traces and metrics on startup
`processor_service` MUST initialize OpenTelemetry providers for traces and metrics during service startup when OTel is enabled.

#### Scenario: OTel enabled startup
- **WHEN** `OTEL_ENABLED=true` and `processor_service` starts
- **THEN** the service MUST initialize trace and metric providers before consuming NATS tasks

#### Scenario: OTel disabled startup
- **WHEN** `OTEL_ENABLED=false` and `processor_service` starts
- **THEN** the service MUST skip exporter initialization and continue normal task processing

### Requirement: Processor service MUST emit structured JSON logs to stdout
`processor_service` MUST emit application logs as structured JSON lines to stdout for container log collection.

#### Scenario: Structured stdout logging
- **WHEN** processor emits an application log event
- **THEN** the log output MUST be written to stdout in JSON format including stable service metadata fields

#### Scenario: No in-process OTel log exporter requirement
- **WHEN** processor startup configures telemetry
- **THEN** processor MUST NOT require in-process OTel log exporter initialization for log delivery

### Requirement: Processor service MUST emit trace spans for task lifecycle
`processor_service` MUST produce trace spans for NATS consume, decode/resolve, enqueue, and tagger run boundaries.

#### Scenario: NATS consume trace
- **WHEN** processor receives a task message from NATS
- **THEN** processor MUST emit spans covering decode and local queue enqueue path

#### Scenario: Tagger execution trace
- **WHEN** processor executes a tagger run batch
- **THEN** processor MUST emit spans for batch run start, completion, and failure outcomes

### Requirement: Processor service MUST expose pipeline metrics
`processor_service` MUST emit low-cardinality metrics for queue depth, task outcomes, retries, and processing latency.

#### Scenario: Queue depth and outcome metrics
- **WHEN** queue items are enqueued, retried, or completed
- **THEN** processor MUST record queue depth and outcome counters

#### Scenario: Tagger latency metrics
- **WHEN** a tagger batch is executed
- **THEN** processor MUST record batch latency metrics and success/failure counts
