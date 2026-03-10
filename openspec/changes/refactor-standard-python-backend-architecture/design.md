## Context

The repository already runs as two independent services (`data-logger`, `data-processor`) but entrypoint files and Dockerfiles were historically located at repository root. This increased ambiguity over service ownership and made it harder to understand which files belong to each runtime. The refactor standardizes service boundaries by colocating entrypoints and Dockerfiles under service folders while preserving backward-compatible root wrappers.

## Goals / Non-Goals

**Goals:**
- Establish explicit per-service module roots: `services/data_logger/` and `services/data_processor/`.
- Establish per-service Dockerfiles in matching folders.
- Keep existing root entry script invocations working through compatibility shims.
- Update compose and project scripts to point at new canonical paths.

**Non-Goals:**
- No behavior changes to NapCat event parsing, persistence, image pipeline, or NATS processing.
- No API/protocol changes to external integrations.
- No deployment topology changes beyond Dockerfile path relocation.

## Decisions

- **Decision: service module entrypoints live under `services/`**  
  Rationale: mirrors common Python backend layout where each runtime has a dedicated module path and canonical `python -m` startup target.

- **Decision: root scripts are retained as wrappers**  
  Rationale: prevents breakage for existing local scripts and external tooling that still invokes historical root files.

- **Decision: Dockerfiles move next to service code**  
  Rationale: improves discoverability and reduces cognitive distance between entrypoint logic and image build configuration.

- **Decision: compose uses `dockerfile: services/<service>/Dockerfile` with root context**  
  Rationale: allows Dockerfiles to remain service-scoped while still copying shared repository modules (`plugins/`, `telemetry.py`, `requirements.txt`) from a single build context.

## Risks / Trade-offs

- **[Risk] Legacy scripts might still import old root modules directly** -> **Mitigation:** keep wrappers (`bot.py`, `data_logger_service.py`, `data_processor_service.py`, `napcat_logger_service.py`) forwarding to new module paths.
- **[Risk] Docker build failures due to changed Dockerfile location** -> **Mitigation:** keep compose build context as `.` and validate with `docker compose config --quiet`.
- **[Risk] Developer confusion during transition** -> **Mitigation:** update README and AGENTS run commands to canonical `python -m services...` form.

## Migration Plan

1. Create `services/data_logger` and `services/data_processor` modules with canonical `main.py` entrypoints.
2. Rewrite root entry scripts to compatibility wrappers importing from service modules.
3. Move Dockerfiles into service folders and update compose dockerfile paths.
4. Update `pyproject.toml` scripts and README/AGENTS run instructions.
5. Validate with unit tests, compileall, and compose config checks.

Rollback strategy:
- Restore root Dockerfiles and prior compose `dockerfile` values.
- Restore root entrypoint implementations from git history.
