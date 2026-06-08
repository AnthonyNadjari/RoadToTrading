"""Recruitee public offers API.

    https://{token}.recruitee.com/api/offers/
"""
from __future__ import annotations

from .base import Scraper, http_get_json
from ..models import RawPosting


class RecruiteeScraper(Scraper):
    name = "recruitee"

    def fetch(self, employer: dict) -> list[RawPosting]:
        token = employer["token"]
        url = f"https://{token}.recruitee.com/api/offers/"
        data = http_get_json(url)
        out: list[RawPosting] = []
        for j in data.get("offers", []):
            city = j.get("city") or ""
            country = j.get("country") or ""
            loc = ", ".join([p for p in (city, country) if p])
            locs = [loc] if loc else []
            for L in j.get("locations") or []:
                if isinstance(L, dict) and L.get("city"):
                    locs.append(L["city"])
            out.append(RawPosting(
                source=self.name,
                employer_id=employer["id"],
                employer_name=employer["name"],
                external_id=str(j.get("id", "")),
                url=j.get("careers_url") or j.get("careers_apply_url", ""),
                raw_title=(j.get("title") or "").strip(),
                locations=list(dict.fromkeys(locs)),
                department=j.get("department"),
                updated_at=j.get("updated_at"),
                posted_at=j.get("published_at") or j.get("created_at"),
            ))
        return out
