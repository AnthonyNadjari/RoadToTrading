"""Lever postings API (public).

    https://api.lever.co/v0/postings/{token}?mode=json
"""
from __future__ import annotations

from datetime import datetime, timezone

from .base import Scraper, http_get_json
from ..models import RawPosting


def _ms_to_iso(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


class LeverScraper(Scraper):
    name = "lever"

    def fetch(self, employer: dict) -> list[RawPosting]:
        token = employer["token"]
        url = f"https://api.lever.co/v0/postings/{token}"
        data = http_get_json(url, params={"mode": "json"})
        out: list[RawPosting] = []
        for j in data:
            cats = j.get("categories") or {}
            loc = cats.get("location") or ""
            extra_locs = cats.get("allLocations") or []
            locs = list(dict.fromkeys([loc, *extra_locs])) if loc else list(extra_locs)
            out.append(RawPosting(
                source=self.name,
                employer_id=employer["id"],
                employer_name=employer["name"],
                external_id=str(j.get("id", "")),
                url=j.get("hostedUrl") or j.get("applyUrl", ""),
                raw_title=(j.get("text") or "").strip(),
                locations=[l for l in locs if l],
                department=cats.get("team"),
                updated_at=_ms_to_iso(j.get("createdAt")),
                posted_at=_ms_to_iso(j.get("createdAt")),
            ))
        return out
