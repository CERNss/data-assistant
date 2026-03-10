## Why

Logger and processor are already separated by process, but they are still coupled through shared filesystem paths and fallback queue behavior. To achieve true service isolation and independent deployment, cross-service interaction must rely only on a versioned NATS contract.

## What Changes

- Introduce a shared, versioned NATS task contract package used by both publisher and consumer.
- **BREAKING**: Replace cross-service `image_path` payload coupling with NATS-resolvable image references and metadata (no shared volume dependency between services).
- Move logger fallback behavior away from processor-local queue APIs so logger only ingests, persists, and publishes.
- Add processor-side resolution flow for contract references before tagging execution.
- Define migration-compatible dual-read/dual-write behavior during rollout and remove legacy path-coupled mode after validation.

## Capabilities

### New Capabilities
- `nats-only-service-contract`: Versioned NATS payload contract for logger->processor task exchange without shared filesystem assumptions.
- `logger-processor-runtime-decoupling`: Runtime isolation rules ensuring logger and processor communicate only through NATS protocol boundaries.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `plugins/napcat/pipeline.py`
  - `plugins/chat_image/nats_task_bus.py`
  - `plugins/chat_image/tagger_worker.py`
  - `plugins/chat_image/tagger_pipeline.py`
  - `docker-compose.yml`
  - `README.md`
- New code:
  - Shared contract module (schema + encode/decode + versioning)
  - Migration compatibility adapters for old/new payload formats
- Runtime:
  - Removes cross-service shared-path dependency as a required coupling mechanism
  - Keeps NATS as the only inter-service communication channel
