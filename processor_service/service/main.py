from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from typing import Any

from loguru import logger

from . import telemetry
from .chat_image.tagger_worker import _run as _run_tagger_worker
from .health import run_health_server


def _install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _request_shutdown(sig: signal.Signals) -> None:
        if stop_event.is_set():
            return
        logger.info("Received {}. Starting graceful shutdown...", sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown, sig)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(
                    sig,
                    lambda _signum, _frame, _sig=sig: _request_shutdown(_sig),
                )
            except ValueError:
                continue


async def _wait_for_shutdown(task: asyncio.Task[Any], timeout_sec: float = 10.0) -> None:
    if task.done():
        return
    try:
        await asyncio.wait_for(task, timeout=timeout_sec)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def _main() -> int:
    stop_event = asyncio.Event()
    _install_shutdown_handlers(stop_event)

    health_task = asyncio.create_task(
        run_health_server(stop_event=stop_event),
        name="health-server",
    )
    worker_task = asyncio.create_task(
        _run_tagger_worker(process_backlog=True, stop_event=stop_event),
        name="tagger-worker",
    )

    try:
        done, _ = await asyncio.wait(
            {health_task, worker_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if worker_task in done:
            return worker_task.result()

        health_task.result()
        if not stop_event.is_set():
            logger.warning("Health server exited unexpectedly. Stopping worker...")
            stop_event.set()
        return await worker_task
    finally:
        stop_event.set()
        await _wait_for_shutdown(health_task)
        await _wait_for_shutdown(worker_task)


def main() -> None:
    telemetry.init_telemetry()
    telemetry.install_error_hooks()
    result = asyncio.run(_main())
    if isinstance(result, int) and result != 0:
        raise SystemExit(result)


if __name__ == "__main__":
    main()
