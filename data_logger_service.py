from __future__ import annotations

import importlib
import sys
from pathlib import Path


def main() -> None:
    sys.path.insert(0, str((Path(__file__).resolve().parent / "data-logger").resolve()))
    run = getattr(importlib.import_module("service.main"), "run")
    run()


if __name__ == "__main__":
    main()
