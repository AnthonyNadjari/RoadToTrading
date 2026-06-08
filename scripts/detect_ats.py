"""Resolve `ats: unknown` employers by probing every supported provider.

    python -m scripts.detect_ats

Writes data/ats_detection.json. Review hits, then add `ats:`/`token:` to
config/employers.yaml (kept a manual step to protect the curated config).
"""
from __future__ import annotations

import logging
import sys

from jobintel.detect import detect_all


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s | %(message)s",
                        datefmt="%H:%M:%S")
    results = detect_all()
    print(f"\n{len(results)} candidate ATS endpoint(s) detected "
          f"-> data/ats_detection.json")
    for r in results:
        print(f"  {r['employer_id']:16s} {r['ats']:14s} {r['token']:24s} "
              f"({r['count']} jobs) e.g. {r['sample_title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
