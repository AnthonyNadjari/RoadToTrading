"""Workable public widget API.

    https://apply.workable.com/api/v1/widget/accounts/{token}?details=true

NOTE: this endpoint returns an account name even for unrelated/empty accounts,
so detect_ats verifies there is >=1 real job before trusting a token.
"""
from __future__ import annotations

from .base import Scraper, http_get_json
from ..models import RawPosting


class WorkableScraper(Scraper):
    name = "workable"

    def fetch(self, employer: dict) -> list[RawPosting]:
        token = employer["token"]
        url = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
        data = http_get_json(url, params={"details": "true"})
        out: list[RawPosting] = []
        for j in data.get("jobs", []):
            city = j.get("city") or ""
            country = j.get("country") or ""
            loc = ", ".join([p for p in (city, country) if p])
            out.append(RawPosting(
                source=self.name,
                employer_id=employer["id"],
                employer_name=employer["name"],
                external_id=str(j.get("shortcode") or j.get("code") or ""),
                url=j.get("url") or j.get("application_url", ""),
                raw_title=(j.get("title") or "").strip(),
                locations=[loc] if loc else [],
                department=j.get("department"),
                posted_at=j.get("created_at") or j.get("published_on"),
            ))
        return out
