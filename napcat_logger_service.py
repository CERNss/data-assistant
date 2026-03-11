from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _load_service_main_module():
    sys.path.insert(0, str((Path(__file__).resolve().parent / "data-logger").resolve()))
    return importlib.import_module("service.main")


def main() -> None:
    run = getattr(_load_service_main_module(), "run")
    run()


def run() -> None:
    main()


if __name__ == "__main__":
    run()
