"""Main crawl entrypoint (run twice a day by GitHub Actions).

    python -m scripts.run_crawl
"""
from __future__ import annotations

import logging
import sys

from jobintel.pipeline import run_crawl
from jobintel.export import build_frontend


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("jobintel.run")
    meta = run_crawl()
    feed = build_frontend()
    log.info("frontend feed: %s", feed)

    # Surface unhealthy sources prominently (monitoring without paid tooling).
    bad = {eid: h for eid, h in meta.get("source_health", {}).items()
           if h.get("consecutive_failures", 0) >= 2}
    if bad:
        log.warning("SOURCES MUTE (>=2 consecutive failures): %s", list(bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
