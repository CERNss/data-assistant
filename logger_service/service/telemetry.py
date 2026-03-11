from __future__ import annotations

import atexit
import asyncio
import logging
import os
import sys
import threading
from typing import Any

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider


_initialized = False
_hooks_installed = False
_loguru_bridged = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_headers(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    headers: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key:
            headers[key] = val
    return headers


def init_telemetry() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    if not _env_bool("OTEL_ENABLED", False):
        logging.getLogger(__name__).info("OTel disabled by OTEL_ENABLED")
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
    insecure = _env_bool("OTEL_EXPORTER_OTLP_INSECURE", True)
    headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
    service_name = os.getenv("OTEL_SERVICE_NAME", "data-assistant-logger")
    resource = Resource.create({"service.name": service_name})

    span_exporter = OTLPSpanExporter(
        endpoint=endpoint, insecure=insecure, headers=headers
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    log_exporter = OTLPLogExporter(
        endpoint=endpoint, insecure=insecure, headers=headers
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    root_logger = logging.getLogger()
    root_logger.addHandler(
        LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    )
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    _bridge_loguru_to_logging()

    logging.getLogger(__name__).info(
        "OTel initialized endpoint=%s service=%s insecure=%s",
        endpoint,
        service_name,
        insecure,
    )

    def _shutdown() -> None:
        provider = trace.get_tracer_provider()
        if not isinstance(provider, NoOpTracerProvider):
            shutdown = getattr(provider, "shutdown", None)
            if callable(shutdown):
                shutdown()
        logger_provider.shutdown()

    atexit.register(_shutdown)


def install_error_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True

    python_old_hook = sys.excepthook
    threading_old_hook = threading.excepthook
    logger = logging.getLogger("runtime.unhandled")

    def _python_excepthook(exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            python_old_hook(exc_type, exc, tb)
            return
        logger.error("Unhandled exception: %s", exc)
        python_old_hook(exc_type, exc, tb)

    def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type and issubclass(args.exc_type, KeyboardInterrupt):
            threading_old_hook(args)
            return
        logger.error(
            "Unhandled thread exception in %s",
            args.thread.name if args.thread else "unknown-thread",
        )
        threading_old_hook(args)

    sys.excepthook = _python_excepthook
    threading.excepthook = _threading_excepthook

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    loop_old_handler = loop.get_exception_handler()

    def _asyncio_exception_handler(
        loop_obj: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        exc = context.get("exception")
        message = context.get("message", "Unhandled asyncio exception")
        logger.error("Asyncio exception: %s", message)
        if loop_old_handler:
            loop_old_handler(loop_obj, context)
        else:
            loop_obj.default_exception_handler(context)

    loop.set_exception_handler(_asyncio_exception_handler)


def _bridge_loguru_to_logging() -> None:
    global _loguru_bridged
    if _loguru_bridged:
        return
    try:
        from loguru import logger as loguru_logger
    except Exception:
        return

    def _sink(message: Any) -> None:
        record = message.record
        logging.getLogger(record["name"]).log(record["level"].no, record["message"])

    loguru_logger.add(_sink, level="INFO")
    _loguru_bridged = True
