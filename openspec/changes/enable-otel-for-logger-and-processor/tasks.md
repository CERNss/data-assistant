## 1. Telemetry Bootstrap and Configuration

- [ ] 1.1 Add `processor_service/service/telemetry.py` with OTel traces/metrics initialization and fail-open behavior
- [ ] 1.2 Normalize OTel env parsing contract in both services (`OTEL_ENABLED`, endpoint, headers, insecure, service name) for traces/metrics
- [ ] 1.3 Wire telemetry startup hooks in `processor_service/service/main.py` to mirror logger startup behavior
- [ ] 1.4 Normalize logger/processor JSON stdout log format and ensure stable service metadata fields
- [ ] 1.5 Ensure logger telemetry module remains service-local and idempotent across repeated initialization calls

## 2. Logger Instrumentation

- [ ] 2.1 Add/verify spans for logger event lifecycle (receive, parse, persist, image processing)
- [ ] 2.2 Add/verify spans for logger NATS publish attempt and result status
- [ ] 2.3 Add logger metrics for ingest throughput, download/persist outcomes, publish outcomes, and latency
- [ ] 2.4 Ensure logger metric attributes are low-cardinality and exclude message/image identifiers

## 3. Processor Instrumentation

- [ ] 3.1 Add spans for processor NATS consume, payload decode/resolve, and queue enqueue flow
- [ ] 3.2 Add spans for processor tagger batch execution and outcome handling
- [ ] 3.3 Add processor metrics for queue depth, retries, task outcomes, and batch latency
- [ ] 3.4 Ensure processor metric attributes are low-cardinality and stable across runs

## 4. Documentation and Operational Wiring

- [ ] 4.1 Update `README.md` with dual-service OTel setup and required/optional environment variables
- [ ] 4.2 Update `AGENTS.md` with service-specific OTel observability run notes
- [ ] 4.3 Add Fluent Bit service and config (`fluent-bit/fluent-bit.conf`, `fluent-bit/parsers.conf`) in `docker-compose.yml` for stdout JSON -> OTLP forwarding
- [ ] 4.4 Configure Fluent Bit healthcheck and set `depends_on: condition: service_healthy` for logger/processor
- [ ] 4.5 Configure logger/processor Docker logging driver to `fluentd` with `fluentd-address: fluent-bit:24224` and service-specific tags
- [ ] 4.6 Update `docker-compose.yml` environment guidance/examples to include both services' OTel config and Fluent Bit OTLP output settings

## 5. Verification

- [ ] 5.1 Add or update unit tests for telemetry bootstrap behavior and fail-open semantics
- [ ] 5.2 Add or update tests validating trace/metric instrumentation touchpoints in logger and processor paths
- [ ] 5.3 Run `python3 -m compileall logger_service processor_service contracts tests`
- [ ] 5.4 Run `python3 -m unittest discover -s tests -p 'test_*.py'`
- [ ] 5.5 Run `docker compose config --quiet` with required env file values
- [ ] 5.6 Validate Fluent Bit healthcheck and service startup ordering under compose
- [ ] 5.7 Validate Fluent Bit pipeline locally: JSON logs from logger/processor are forwarded to OTLP collector/backend
