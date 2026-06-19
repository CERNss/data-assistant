from __future__ import annotations

import argparse
import asyncio

from .config import load_chat_image_config
from .tagger_pipeline import get_pending_tagger_count, run_tagger_once, run_tagger_until_empty


async def _run(once: bool) -> int:
    config = load_chat_image_config()
    if not config.tagger.enabled:
        print("CHAT_IMAGE_TAGGER_ENABLED is false, skip tagging.")
        return 0
    if not config.tagger.base_url:
        print("CHAT_IMAGE_TAGGER_BASE_URL is empty, skip tagging.")
        return 1

    pending_before = get_pending_tagger_count(config)
    if once:
        summary = await run_tagger_once(config)
    else:
        summary = await run_tagger_until_empty(config)
    pending_after = get_pending_tagger_count(config)

    print(
        "tagger summary:",
        f"pending_before={pending_before}",
        f"picked={summary['picked']}",
        f"success={summary['success']}",
        f"failed={summary['failed']}",
        f"requeued={summary['requeued']}",
        f"pending_after={pending_after}",
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run chat image tagger queue.")
    parser.add_argument("--once", action="store_true", help="Process only one batch.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.once)))


if __name__ == "__main__":
    main()
