from __future__ import annotations

import asyncio

import aiohttp
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from .config import ChatImageConfig


TRACER = trace.get_tracer("data_assistant.plugins.chat_image.downloader")


async def download_image_bytes_with_retry(url: str, config: ChatImageConfig) -> tuple[bytes, int]:
    attempts = max(1, config.retry_count)
    with TRACER.start_as_current_span(
        "chat_image.download",
        attributes={
            "chat.image.url": url,
            "chat.image.max_attempts": attempts,
        },
    ) as span:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            span.add_event("chat_image.download.attempt", {"attempt": attempt})
            try:
                return await _download_image_bytes(url, config.timeout_sec), attempt
            except Exception as exc:
                last_error = exc
                if attempt < attempts:
                    await asyncio.sleep(config.retry_delay_sec)
        assert last_error is not None
        span.record_exception(last_error)
        span.set_status(Status(status_code=StatusCode.ERROR, description=str(last_error)))
        raise RuntimeError(f"download failed after {attempts} attempts: {last_error}") from last_error


async def _download_image_bytes(url: str, timeout_sec: float) -> bytes:
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()
