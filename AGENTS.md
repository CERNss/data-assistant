# Agents Guide (data-assistant)

This repo is a small Python service app that ingests NapCat OneBot11 events, archives chat images,
and optionally publishes tagging tasks to NATS for an external image tagger worker.

No Cursor rules were found in `.cursor/rules/` or `.cursorrules`.
No Copilot rules were found in `.github/copilot-instructions.md`.

## Commands

### Setup (local dev)

- Create venv (recommended):
  - `python -m venv .venv`
  - `source .venv/bin/activate`
- Install runtime deps:
  - `python -m pip install -U pip`
  - `python -m pip install -r requirements.txt`

Python requirement: `>=3.10` (Dockerfiles use `python:3.11-slim`).

### Run (local)

- Logger service (NapCat reverse WS server):
  - `python3 -m logger_service.service.main`
- Processor service (tagger worker):
  - `python3 -m processor_service.service.main`
  - or `python3 -m processor_service.service.chat_image.tagger_worker`
- Manual local tagging (no NATS):
  - `python3 -m processor_service.service.chat_image.tagger_cli`
  - one batch: `python3 -m processor_service.service.chat_image.tagger_cli --once`

### Docker Compose (logger + processor + NATS)

- Prepare env:
  - `cp .env.example .env`
  - set `CHAT_IMAGE_TAGGER_TOOL_ROOT_HOST` in `.env` (host path to Eagle_AItagger_byWD1.4)
- Start (recommended order):
  - `docker compose up -d nats fluent-bit processor`
  - `docker compose up -d logger`
- Logs: `docker compose logs -f logger processor fluent-bit nats`
- Stop: `docker compose down`

### Tests

Tests are `unittest`-based (including async via `unittest.IsolatedAsyncioTestCase`).

- Run all tests:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`

- Run a single test module:
  - `python3 -m unittest tests.test_chat_image_storage`

- Run a single test class:
  - `python3 -m unittest tests.test_chat_image_tagger_worker.TestChatImageTaggerWorker`

- Run a single test method:
  - `python3 -m unittest tests.test_chat_image_tagger_pipeline.TestChatImageTaggerPipeline.test_run_once_success`

### Lint / Format

There is no repo-pinned linter/formatter config (no `ruff.toml`, `pyproject` tool config, etc.).

- Minimal sanity check:
  - `python3 -m compileall .`

- Optional (if you install ruff locally):
  - `python -m pip install ruff`
  - `ruff check .`
  - `ruff format .`

## Code Style (follow existing patterns)

### Imports

- If a module uses postponed annotations, keep `from __future__ import annotations` as the first import.
- Group imports: stdlib, third-party, then local.
- Prefer package-relative imports inside service packages (e.g. `from .audit import ...`).
- Tests typically import via the repo root package path (e.g. `from logger_service.service...` or `from processor_service.service...`).

### Formatting

- Use 4-space indentation; keep formatting Black-compatible (trailing commas in multi-line literals).
- Prefer f-strings for string composition; keep log messages parameterized (see Logging).
- Use `Path` over raw strings for filesystem paths.

### Types

- Use modern annotations: `list[T]`, `dict[str, Any]`, `X | None`.
- Add return types on public functions and tests (`-> None`), as the codebase does.
- Use `Any` sparingly; validate untyped inputs at boundaries (e.g. decoded JSON, NATS messages).

### Naming

- Functions/vars: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE_CASE`.
- Keep env var names stable and documented; config parsing lives in service-scoped modules under `logger_service/service/chat_image/` and `processor_service/service/chat_image/`.
- Tracer names follow dotted paths like `data_assistant.<service>.<module>`.

### Logging and Tracing

- Use Loguru-style `{}` formatting in service code:
  - `logger.info("Saved chat image: path={} size={}", path, size)`
- Logger/processor runtime logs are emitted as JSON to stdout and forwarded by Fluent Bit.
- Traces and metrics are exported via in-process OpenTelemetry SDK OTLP exporters.
- Wrap meaningful operations with OpenTelemetry spans when appropriate (pattern in `logger_service/service/napcat/pipeline.py`).

### Error Handling

- Prefer specific exceptions (`ValueError` for invalid payloads, `RuntimeError` for misconfiguration).
- Catch broad `Exception` only at system boundaries (event handlers, message processing, subprocess calls).
- When re-raising, use exception chaining: `raise RuntimeError("...") from exc`.
- On recoverable failures, log and continue; avoid crashing long-running services.

### I/O and Data Files

- Runtime output goes under `data/` (gitignored). Do not commit generated `.jsonl` logs or queues.
- JSON output uses UTF-8 and `ensure_ascii=False` (see `logger_service/service/chat_image/audit.py`).
- When persisting structured state, prefer atomic writes (write tmp + replace) as done for tagger queue.

### Async / Concurrency

- Keep QQ handlers non-blocking; do network I/O with `aiohttp` and use retries (`downloader.py`).
- Protect shared on-disk queue state with `asyncio.Lock` (`tagger_pipeline.py`).
- Offload blocking work (subprocess, heavy I/O) via `asyncio.to_thread`.

### Tests

- Use `unittest` (not pytest) unless the repo explicitly adopts it.
- Prefer hermetic tests: use `tempfile.TemporaryDirectory()` and avoid touching `data/`.
- For async tests, inherit from `unittest.IsolatedAsyncioTestCase`.

## Repo-Specific Gotchas

- `docker-compose.yml` mounts a shared `/app/data` volume for logger + processor; paths must match.
- Fluent Bit config files live at `fluent-bit/fluent-bit.conf` and `fluent-bit/parsers.conf`; compose mounts both read-only.
- Docker build context ignores `tests/` and `openspec/` (`.dockerignore`), so containers cannot run tests.
- Secrets live in `.env`; never commit real QQ credentials or tokens.
- NATS publishing is best-effort; when no worker is subscribed, messages can be lost (core pub/sub semantics).

## Agent Workflow Notes

This repo includes an OpenSpec-based workflow under `openspec/` with helper prompts in:
- `.opencode/command/` (opsx commands)
- `.opencode/skills/` (skill instructions)
- `.claude/commands/` and `.claude/skills/` (similar content for other agents)

If a task references an “OpenSpec change”, look under `openspec/changes/<change-name>/`.
