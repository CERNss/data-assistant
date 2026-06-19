## 1. OpenSpec Artifacts

- [x] 1.1 Add `nats-only-service-contract` capability spec
- [x] 1.2 Add `logger-processor-runtime-decoupling` capability spec
- [x] 1.3 Confirm proposal/design/spec/tasks artifacts are complete and consistent

## 2. Shared Contract Package

- [x] 2.1 Create `contracts/chat_image_task.py` with versioned task schema (`v2`) and validators
- [x] 2.2 Implement encode/decode helpers with UTF-8 JSON and validation errors
- [x] 2.3 Support v1 payload decode compatibility during migration window

## 3. Canonical Dual Top-Level Service Layout

- [x] 3.1 Create `logger_service/service` canonical runtime package and move logger-owned modules
- [x] 3.2 Create `processor_service/service` canonical runtime package and move processor-owned modules
- [x] 3.3 Add service-scoped Dockerfiles at `logger_service/Dockerfile` and `processor_service/Dockerfile`
- [x] 3.4 Remove root compatibility wrappers and use canonical service modules only

## 4. NATS-Only Runtime Decoupling

- [x] 4.1 Remove logger dependency on processor-local queue fallback APIs
- [x] 4.2 Update logger publish path to use shared contract package
- [x] 4.3 Update processor consume path to decode shared contract (`v2`) and accept legacy (`v1`)
- [x] 4.4 Remove path-coupled contract assumptions from cross-service payload shape

## 5. Wiring and Documentation

- [x] 5.1 Update `docker-compose.yml` to top-level service Dockerfile paths
- [x] 5.2 Update `pyproject.toml` scripts and runtime module references
- [x] 5.3 Update `README.md` and `AGENTS.md` to dual top-level service layout

## 6. Verification

- [x] 6.1 Run `python -m compileall logger_service processor_service contracts`
- [x] 6.2 Run `python -m unittest discover -s tests -p 'test_*.py'`
- [x] 6.3 Run `docker compose config --quiet`
- [x] 6.4 Verify no cross-service imports and no legacy `services/`/`plugins/` runtime coupling remains
