from __future__ import annotations

from . import telemetry
from .chat_image.tagger_worker import main as run_tagger_worker


def main() -> None:
    telemetry.init_telemetry()
    telemetry.install_error_hooks()
    run_tagger_worker()


if __name__ == "__main__":
    main()
