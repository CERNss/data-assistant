## Why

The service entrypoints and container definitions were previously mixed at repository root, which made it harder to distinguish logger and processor ownership. We need explicit per-service folders so local development, Docker build paths, and maintenance boundaries match the two-service runtime model.

## What Changes

- Split runtime entry modules into dedicated service folders: `services/data_logger/` and `services/data_processor/`.
- Move service Dockerfiles into service folders and update Compose to build from service-scoped Dockerfiles.
- Keep root compatibility wrappers (`bot.py`, `data_logger_service.py`, `data_processor_service.py`, `napcat_logger_service.py`) delegating to new service modules.
- Update project scripts and docs to use `python -m services...` entrypoint style.

## Capabilities

### New Capabilities
- `service-entrypoint-layout`: Standardized per-service module layout for logger/processor runtime bootstrapping.
- `service-scoped-container-build`: Service-scoped Dockerfile locations with compose wiring to those paths.

### Modified Capabilities
- None.

## Impact

- Affected code: service entry scripts, docker-compose build paths, package scripts, developer run documentation.
- Affected container build files: root Dockerfiles removed, new Dockerfiles added under `services/`.
- No protocol-level changes to NapCat ingestion, persistence, or NATS task payload contracts.
