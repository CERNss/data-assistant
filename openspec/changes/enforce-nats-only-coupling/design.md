## Context

The codebase has already separated logger and processor entry logic, but there are still coupling points that violate NATS-only interaction: path-based payloads (`image_path`) and fallback behavior that reaches processor-local queue APIs from logger code. In addition, the desired runtime layout is explicit dual top-level service directories (`data-logger/service`, `data-processor/service`) so ownership and deployment boundaries are visually and operationally clear.

## Goals / Non-Goals

**Goals:**
- Enforce NATS as the only cross-service communication boundary.
- Remove mandatory shared-filesystem contract between logger and processor.
- Establish dual top-level service layout:
  - `data-logger/service`
  - `data-processor/service`
- Keep backward compatibility during migration with controlled dual-format support.

**Non-Goals:**
- No changes to tagger model algorithm or output schema.
- No replacement of NATS with another broker.
- No large-scale database schema redesign beyond fields needed for new transport references and migration traceability.

## Decisions

### 1) Dual top-level service directories are the canonical runtime layout
- Decision: move canonical runtime entrypoints and per-service Dockerfiles under:
  - `data-logger/service/main.py`
  - `data-processor/service/main.py`
  - `data-logger/Dockerfile`
  - `data-processor/Dockerfile`
- Rationale: this matches the desired operational mental model (two deployable services) better than a shared `services/` root.
- Alternative considered: keep `services/data_logger` and `services/data_processor`; rejected because it weakens explicit top-level ownership requested by stakeholders.

### 2) Introduce a shared, versioned contract module for NATS payload
- Decision: create a shared contract package (e.g. `contracts/chat_image_task.py`) that defines payload versions, validation, and encode/decode logic for both producer and consumer.
- Rationale: centralizing protocol definitions avoids drift between logger publisher and processor consumer.
- Alternative considered: duplicate schema code in each service; rejected due drift risk and higher migration cost.

### 3) Replace path-coupled payload with broker-resolvable image reference
- Decision: deprecate required `image_path` contract and add versioned payload with reference fields and metadata suitable for NATS-only transfer semantics.
- Rationale: a pure path contract assumes shared filesystem and prevents independent deployment.
- Alternative considered: keep shared volume as permanent coupling; rejected because it contradicts NATS-only objective.

### 4) Keep migration-safe dual-read/dual-write window
- Decision: during rollout, logger can publish new payload while optionally preserving old format for compatibility; processor supports both until cutover completes.
- Rationale: avoids hard cutovers and reduces outage risk.
- Alternative considered: one-step hard break; rejected due operational risk.

### 5) Remove logger-side dependency on processor local queue APIs
- Decision: logger no longer calls processor-local queue helpers (`tagger_pipeline` enqueue paths). Logger responsibility ends at ingest/persist/publish and publisher status persistence.
- Rationale: prevents hidden runtime coupling and keeps responsibilities clear.

## Risks / Trade-offs

- [Risk] Contract migration introduces temporary complexity (dual formats) -> Mitigation: explicit version field, migration window, and removal criteria in tasks.
- [Risk] Delivery semantics change can increase duplicate processing -> Mitigation: idempotency keys (`image_id`, `sha256`) and consumer-side dedup checks.
- [Risk] Splitting by directories may break old script paths -> Mitigation: keep root compatibility wrappers that delegate to canonical `data-logger/service` and `data-processor/service` entrypoints.
- [Risk] Runtime behavior divergence between environments -> Mitigation: enforce compose and CI validation (`docker compose config`, unit/integration contract tests).

## Migration Plan

1. Create/confirm canonical dual top-level directories and entrypoints (`data-logger/service`, `data-processor/service`).
2. Introduce `contracts` package for versioned NATS task schema.
3. Update logger publish path to new contract while persisting migration telemetry.
4. Update processor consume path to support both old and new contract versions.
5. Remove logger calls into processor-local queue APIs.
6. Remove path-coupled mode and shared-volume dependency as required coupling once cutover criteria are met.

Rollback strategy:
- Re-enable old payload format publish/consume compatibility and retain wrapper entrypoints.
- Keep previous compose volume mapping only as temporary rollback path (not target steady state).

## Open Questions

- Should the new NATS-only transport use JetStream object references as the default contract target, or keep a simpler transitional reference format first?
- What exact cutover condition marks removal of old `image_path` payload support (time-window vs success-rate threshold)?
