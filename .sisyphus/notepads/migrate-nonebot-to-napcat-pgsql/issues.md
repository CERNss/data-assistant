# Issues

## [2026-03-10] Pre-existing LSP errors in telemetry.py (DO NOT FIX — out of scope)
- `set_logger_provider` unknown import symbol
- `TracerProvider.shutdown` attribute unknown
- `exc_info` type mismatch in `logger.error`
- `message.record` attribute unknown on str
These are pre-existing type-stub issues in the existing codebase. Do NOT touch `telemetry.py`.
