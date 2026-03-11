## Why

Current observability is incomplete and inconsistent across `logger_service` and `processor_service`. We need end-to-end OpenTelemetry coverage now so both services emit logs, traces, and metrics with consistent resource/service metadata and exporter configuration.

## What Changes

- Add production-ready OTel initialization for both `logger_service` and `processor_service`.
- Standardize trace instrumentation for key runtime flows (event ingest, NATS publish/consume, tagger pipeline execution).
- Add metrics emission for throughput, failures, retries, queue depth, and processing latency.
- Route application logs to container stdout in structured JSON format, and forward via Fluent Bit using OTLP.
- Normalize env-based OTel configuration across both services (endpoint, headers, protocol, service name, enable flags).
- Update Docker Compose/runtime wiring to include Fluent Bit log forwarding while keeping traces/metrics via service-side OTel SDK.
  - Fluent Bit runs as a dedicated compose service.
  - Business services use Docker `logging.driver: fluentd` with `fluentd-address: fluent-bit:24224`.
  - Startup ordering uses `depends_on` with `condition: service_healthy` for Fluent Bit.

## Capabilities

### New Capabilities
- `logger-service-otel-observability`: Full OTel logs/traces/metrics behavior for logger runtime.
- `processor-service-otel-observability`: Full OTel logs/traces/metrics behavior for processor runtime.
- `otel-runtime-configuration`: Shared runtime configuration contract for OTel exporter and resource metadata across services.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `logger_service/service/main.py`
  - `logger_service/service/telemetry.py`
  - `logger_service/service/napcat/pipeline.py`
  - `logger_service/service/chat_image/nats_publisher.py`
  - `processor_service/service/main.py`
  - `processor_service/service/telemetry.py`
  - `processor_service/service/chat_image/tagger_worker.py`
  - `processor_service/service/chat_image/tagger_pipeline.py`
  - `docker-compose.yml`
  - `fluent-bit/fluent-bit.conf`
  - `fluent-bit/parsers.conf`
  - `README.md`
  - `AGENTS.md`
- Affected dependencies/systems:
  - OpenTelemetry SDK/exporters already in `requirements.txt`
  - Fluent Bit container/runtime configuration
  - OTel collector endpoint configuration and deployment environment variables
- Runtime impact:
  - Both services export traces/metrics with aligned resource metadata via OTel SDK
  - Both services emit JSON logs to stdout and logs are forwarded by Fluent Bit via OTLP
  - Improved operational visibility for ingest, dispatch, and tagging pipeline health
