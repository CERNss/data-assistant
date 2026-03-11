## Context

The repository now runs as two independent service roots: `logger_service` and `processor_service`. `logger_service` already contains partial OTel setup (`logger_service/service/telemetry.py`) and trace instrumentation in some logger-side paths, while `processor_service` currently lacks equivalent runtime initialization and consistent log/metric export wiring.

The target change requires both services to expose complete OpenTelemetry observability (logs, traces, metrics) with aligned configuration and service metadata. Existing deployment uses Docker Compose and environment-based runtime configuration, so the design must keep configuration env-driven and deployment-friendly.

The logging pipeline is explicitly container-first: applications emit structured JSON logs to stdout, and Fluent Bit forwards those logs to the OTLP endpoint. Traces and metrics remain service-side OpenTelemetry SDK exporters.

Constraints:
- Keep the current service isolation (`logger_service` vs `processor_service`).
- Avoid reintroducing cross-service runtime coupling.
- Maintain backward-compatible defaults when OTel is disabled.
- Keep current dependencies footprint minimal (reuse existing OpenTelemetry libraries in `requirements.txt`).
- Keep application log transport decoupled from in-process OTel log exporters.

Stakeholders:
- Service operators who need production diagnostics and SLO visibility.
- Developers debugging ingest, publish, consume, and tagging pipeline failures.

## Goals / Non-Goals

**Goals:**
- Enable OTel traces and metrics in both `logger_service` and `processor_service` via in-process OTel SDK.
- Emit structured JSON logs to stdout in both services and forward them through Fluent Bit via OTLP.
- Standardize OTel configuration contract (endpoint, headers, protocol/insecure mode, service naming, enable flags).
- Instrument critical spans and metrics around NapCat ingest, NATS publish/consume, and tagger execution lifecycle.
- Ensure exporter behavior is robust and does not break service startup when OTel is disabled.

**Non-Goals:**
- No migration to a different telemetry backend.
- No business logic changes to image processing or tagging behavior.
- No redesign of NATS/task contracts beyond telemetry attributes.
- No full distributed context propagation redesign across external systems beyond practical service boundaries.

## Decisions

### 1) Keep service-owned telemetry bootstrap modules
- Decision: keep `logger_service/service/telemetry.py` and add a sibling `processor_service/service/telemetry.py` with equivalent initialization structure.
- Rationale: each service owns startup lifecycle, and local ownership avoids hidden coupling and import-path fragility.
- Alternative considered: one shared `observability/` bootstrap module. Rejected for now to avoid broad refactor and because service-specific lifecycle hooks differ.

### 2) Use Fluent Bit for log forwarding, not in-process OTel log exporter
- Decision: applications write JSON logs to stdout; Fluent Bit sidecar/service collects container logs and forwards to OTLP collector/backend.
- Rationale: this matches container-native operations, reduces in-process logging exporter complexity, and centralizes log transport/retry behavior.
- Alternative considered: in-process OTel `LoggingHandler` and log exporter in each service. Rejected to avoid duplicate pipelines and reduce startup/runtime coupling.

Operational compose pattern (adopted):
- Add a dedicated `fluent-bit` service using `fluent/fluent-bit:latest`.
- Mount config files:
  - `fluent-bit/fluent-bit.conf` -> `/fluent-bit/etc/fluent-bit.conf`
  - `fluent-bit/parsers.conf` -> `/fluent-bit/etc/parsers.conf`
- Run command: `fluent-bit -c /fluent-bit/etc/fluent-bit.conf`.
- Expose Fluentd forward listener on `24224/tcp` and `24224/udp` for Docker logging driver.
- Enable Fluent Bit HTTP server health endpoint and add healthcheck against `/api/v1/health`.
- Set service dependencies: `logger_service` and `processor_service` depend on `fluent-bit` with `condition: service_healthy`.
- Configure service logging section:
  - `logging.driver: fluentd`
  - `logging.options.fluentd-address: fluent-bit:24224`
  - `logging.options.tag`: service-specific tag (e.g., `docker.logger-service`, `docker.processor-service`).

### 3) Standardize OTel configuration environment contract across both services
- Decision: both services read the same core env keys (`OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_INSECURE`, `OTEL_SERVICE_NAME`) for traces/metrics and service-specific defaults when unset.
- Rationale: operators need one predictable configuration model; service-specific default names preserve attribution.
- Alternative considered: service-prefixed env keys only. Rejected due operational complexity and duplication.

### 4) Instrument critical runtime paths first, then broaden
- Decision: instrument key spans/metrics at boundaries:
  - logger: event receive/parse, persistence write, image download, NATS publish
  - processor: NATS message handling, decode/resolve, enqueue/dequeue, tagger run summary
- Rationale: high-signal observability first with bounded implementation risk.
- Alternative considered: exhaustive instrumentation for every function. Rejected due noise and maintenance overhead.

### 5) Add metrics via OTel Meter API with low-cardinality attributes
- Decision: emit counters/histograms/gauges for throughput, failures, retries, queue depth, processing latency, publish success/failure, and tagger outcomes; enforce low-cardinality labels.
- Rationale: metrics should be production-safe and queryable without cardinality explosions.
- Alternative considered: log-derived metrics only. Rejected due delayed detection and weaker alerting.

### 6) Preserve fail-open behavior for telemetry pipeline
- Decision: telemetry/exporter failures must not stop business service startup; log warnings and continue.
- Rationale: observability is critical but must not become a single point of failure.
- Alternative considered: fail-fast when OTel unavailable. Rejected because it harms service availability.

## Risks / Trade-offs

- [Risk] Metric attribute cardinality grows unexpectedly -> Mitigation: restrict labels to stable dimensions (service, outcome, phase) and avoid message/image IDs in metric labels.
- [Risk] Added instrumentation impacts latency -> Mitigation: batch exporters, avoid synchronous flush in hot paths, benchmark key endpoints.
- [Risk] Inconsistent service naming causes split dashboards -> Mitigation: define explicit service naming defaults and document override rules.
- [Risk] Processor telemetry parity lags logger implementation -> Mitigation: include processor bootstrap/instrumentation tasks in same change completion checklist.
- [Risk] Log schema drift across services weakens queryability -> Mitigation: enforce shared JSON log field set and document required fields.
- [Risk] Fluent Bit outage delays log delivery -> Mitigation: use Fluent Bit buffering/retry and keep stdout emission independent from forwarding.
- [Risk] Fluent Bit health endpoint not enabled causes false-unhealthy startup gate -> Mitigation: ensure Fluent Bit config explicitly enables HTTP server on known port and health route.

## Migration Plan

1. Implement processor telemetry bootstrap module and startup hook in `processor_service/service/main.py` (traces/metrics).
2. Normalize logger/processor JSON stdout log format and logging configuration.
3. Add Fluent Bit service and config in Compose for container log collection and OTLP forwarding, including healthcheck and service_healthy dependency gates.
4. Add required spans/metrics in logger critical paths.
5. Add required spans/metrics in processor critical paths.
6. Update compose/docs/env guidance for both services plus Fluent Bit.
7. Validate with local collector setup and regression tests.

Rollback strategy:
- Set `OTEL_ENABLED=false` for both services to disable trace/metric exporters immediately.
- Temporarily disable Fluent Bit service if log forwarding causes runtime issues.
- Revert telemetry bootstrap wiring commits if runtime instability appears.
- Keep core business flow independent from telemetry to allow safe rollback without contract/data changes.

## Open Questions

- Should Fluent Bit OTLP output use gRPC or HTTP/protobuf in default configuration for current collector deployment?
- Should queue depth be emitted as observable gauge on timer collection, or as sampled value during queue mutations only?
- Do we want standardized semantic metric names aligned with internal dashboard conventions before implementation, or in a follow-up documentation pass?
