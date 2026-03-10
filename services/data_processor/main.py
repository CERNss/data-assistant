from __future__ import annotations

from plugins.chat_image.tagger_worker import main as run_tagger_worker


def main() -> None:
    run_tagger_worker()


if __name__ == "__main__":
    main()
