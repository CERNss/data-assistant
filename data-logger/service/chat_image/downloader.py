from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
except ImportError:
    trace = None
    Status = None
    StatusCode = None

from .config import ChatImageConfig


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def add_event(self, name: str, attributes: dict[str, Any]) -> None:
        return None

    def record_exception(self, exc: Exception) -> None:
        return None

    def set_status(self, status: Any) -> None:
        return None


class _NoOpTracer:
    def start_as_current_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> _NoOpSpan:
        return _NoOpSpan()


TRACER = (
    trace.get_tracer("data_assistant.plugins.chat_image.downloader")
    if trace is not None
    else _NoOpTracer()
)


@dataclass(frozen=True)
class DownloadedImage:
    body: bytes
    content_type: str | None
    content_length: int | None


class DownloadError(RuntimeError):
    def __init__(
        self,
        *,
        url: str,
        attempts: int,
        last_error: Exception,
        status_code: int | None,
    ) -> None:
        super().__init__(f"download failed after {attempts} attempts: {last_error}")
        self.url = url
        self.attempts = attempts
        self.last_error = last_error
        self.status_code = status_code


async def download_image_bytes_with_retry(
    url: str, config: ChatImageConfig
) -> tuple[bytes, int]:
    downloaded, attempt = await download_image_with_retry(url, config)
    return downloaded.body, attempt


async def download_image_with_retry(
    url: str,
    config: ChatImageConfig,
) -> tuple[DownloadedImage, int]:
    attempts = max(1, config.retry_count)
    with TRACER.start_as_current_span(
        "chat_image.download",
        attributes={
            "chat.image.url": url,
            "chat.image.max_attempts": attempts,
        },
    ) as span:
        last_error: Exception | None = None
        status_code: int | None = None
        for attempt in range(1, attempts + 1):
            span.add_event("chat_image.download.attempt", {"attempt": attempt})
            try:
                downloaded = await _download_image(url, config.timeout_sec)
                return downloaded, attempt
            except Exception as exc:
                last_error = exc
                if isinstance(exc, aiohttp.ClientResponseError):
                    status_code = exc.status
                if attempt < attempts:
                    await asyncio.sleep(config.retry_delay_sec)
        assert last_error is not None
        span.record_exception(last_error)
        if Status is not None and StatusCode is not None:
            span.set_status(
                Status(status_code=StatusCode.ERROR, description=str(last_error))
            )
        raise DownloadError(
            url=url,
            attempts=attempts,
            last_error=last_error,
            status_code=status_code,
        ) from last_error


async def _download_image(url: str, timeout_sec: float) -> DownloadedImage:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            body = await response.read()
            content_type = response.headers.get("Content-Type")
            content_length_raw = response.headers.get("Content-Length")
            content_length: int | None = None
            if content_length_raw is not None:
                try:
                    content_length = int(content_length_raw)
                except ValueError:
                    content_length = None
            if content_length is None:
                content_length = len(body)
            return DownloadedImage(
                body=body,
                content_type=content_type,
                content_length=content_length,
            )
