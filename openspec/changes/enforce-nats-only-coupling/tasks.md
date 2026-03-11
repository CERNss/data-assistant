## 1. OpenSpec Artifacts

- [ ] 1.1 Add `nats-only-service-contract` capability spec
- [ ] 1.2 Add `logger-processor-runtime-decoupling` capability spec
- [ ] 1.3 Confirm proposal/design/spec/tasks artifacts are complete and consistent

## 2. Shared Contract Package

- [ ] 2.1 Create `contracts/chat_image_task.py` with versioned task schema (`v2`) and validators
- [ ] 2.2 Implement encode/decode helpers with UTF-8 JSON and validation errors
- [ ] 2.3 Support v1 payload decode compatibility during migration window

## 3. Canonical Dual Top-Level Service Layout

- [ ] 3.1 Create `data-logger/service` canonical runtime package and move logger-owned modules
- [ ] 3.2 Create `data-processor/service` canonical runtime package and move processor-owned modules
- [ ] 3.3 Add service-scoped Dockerfiles at `data-logger/Dockerfile` and `data-processor/Dockerfile`
- [ ] 3.4 Keep root compatibility wrappers delegating to canonical top-level service entrypoints

## 4. NATS-Only Runtime Decoupling

- [ ] 4.1 Remove logger dependency on processor-local queue fallback APIs
- [ ] 4.2 Update logger publish path to use shared contract package
- [ ] 4.3 Update processor consume path to decode shared contract (`v2`) and accept legacy (`v1`)
- [ ] 4.4 Remove path-coupled contract assumptions from cross-service payload shape

## 5. Wiring and Documentation

- [ ] 5.1 Update `docker-compose.yml` to top-level service Dockerfile paths
- [ ] 5.2 Update `pyproject.toml` scripts and runtime module references
- [ ] 5.3 Update `README.md` and `AGENTS.md` to dual top-level service layout

## 6. Verification

- [ ] 6.1 Run `python -m compileall data-logger data-processor contracts`
- [ ] 6.2 Run `python -m unittest discover -s tests -p 'test_*.py'`
- [ ] 6.3 Run `docker compose config --quiet`
- [ ] 6.4 Verify no cross-service imports and no legacy `services/`/`plugins/` runtime coupling remains
