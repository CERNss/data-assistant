from __future__ import annotations

import importlib
import sys
from pathlib import Path


def main() -> None:
    sys.path.insert(
        0,
        str((Path(__file__).resolve().parent / "data-processor").resolve()),
    )
    service_main = getattr(importlib.import_module("service.main"), "main")
    service_main()


if __name__ == "__main__":
    main()
