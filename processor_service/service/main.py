from __future__ import annotations

import asyncio

from . import telemetry
from .chat_image.tagger_worker import _run as _run_tagger_worker
from .health import run_health_server


async def _main() -> None:
    await asyncio.gather(
        run_health_server(),
        _run_tagger_worker(process_backlog=True),
    )


def main() -> None:
    telemetry.init_telemetry()
    telemetry.install_error_hooks()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
