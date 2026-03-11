from __future__ import annotations

import atexit
import asyncio
import os
import sys
import threading
from typing import Any

from loguru import logger as loguru_logger


_initialized = False
_hooks_installed = False
_json_logging_configured = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int, *, minimum: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


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


def _setup_json_stdout_logging(default_service_name: str) -> str:
    global _json_logging_configured

    service_name = os.getenv("OTEL_SERVICE_NAME", default_service_name).strip()
    if not service_name:
        service_name = default_service_name

    if _json_logging_configured:
        return service_name

    level = os.getenv("LOG_LEVEL", "INFO").strip() or "INFO"
    loguru_logger.remove()
    loguru_logger.configure(extra={"service": service_name})
    loguru_logger.add(
        sys.stdout,
        serialize=True,
        level=level,
        backtrace=False,
        diagnose=False,
    )
    _json_logging_configured = True
    return service_name


def init_telemetry() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    service_name = _setup_json_stdout_logging("data-assistant-processor")

    if not _env_bool("OTEL_ENABLED", False):
        loguru_logger.info("OTel disabled by OTEL_ENABLED")
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
    insecure = _env_bool("OTEL_EXPORTER_OTLP_INSECURE", True)
    headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
    metric_interval_ms = _env_int(
        "OTEL_METRIC_EXPORT_INTERVAL_MS",
        60000,
        minimum=1000,
    )

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace import NoOpTracerProvider

        resource = Resource.create({"service.name": service_name})

        span_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=insecure,
            headers=headers,
        )
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)

        metric_exporter = OTLPMetricExporter(
            endpoint=endpoint,
            insecure=insecure,
            headers=headers,
        )
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=metric_interval_ms,
        )
        meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)

        def _shutdown() -> None:
            provider = trace.get_tracer_provider()
            if not isinstance(provider, NoOpTracerProvider):
                shutdown = getattr(provider, "shutdown", None)
                if callable(shutdown):
                    shutdown()
            meter_shutdown = getattr(meter_provider, "shutdown", None)
            if callable(meter_shutdown):
                meter_shutdown()

        atexit.register(_shutdown)

        loguru_logger.info(
            "OTel traces/metrics initialized endpoint={} service={} insecure={} metric_interval_ms={}",
            endpoint,
            service_name,
            insecure,
            metric_interval_ms,
        )
    except Exception as exc:
        loguru_logger.warning(
            "OTel initialization failed, continue without exporters: {}",
            exc,
        )


def install_error_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True

    python_old_hook = sys.excepthook
    threading_old_hook = threading.excepthook

    def _python_excepthook(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: Any,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            python_old_hook(exc_type, exc, tb)
            return
        loguru_logger.opt(exception=(exc_type, exc, tb)).error("Unhandled exception")
        python_old_hook(exc_type, exc, tb)

    def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type and issubclass(args.exc_type, KeyboardInterrupt):
            threading_old_hook(args)
            return
        if args.exc_type and args.exc_value is not None:
            loguru_logger.opt(
                exception=(args.exc_type, args.exc_value, args.exc_traceback)
            ).error(
                "Unhandled thread exception in {}",
                args.thread.name if args.thread else "unknown-thread",
            )
        else:
            loguru_logger.error(
                "Unhandled thread exception in {}",
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
        message = str(context.get("message", "Unhandled asyncio exception"))
        exc = context.get("exception")
        if isinstance(exc, BaseException):
            loguru_logger.opt(exception=exc).error("Asyncio exception: {}", message)
        else:
            loguru_logger.error("Asyncio exception: {}", message)
        if loop_old_handler:
            loop_old_handler(loop_obj, context)
        else:
            loop_obj.default_exception_handler(context)

    loop.set_exception_handler(_asyncio_exception_handler)
