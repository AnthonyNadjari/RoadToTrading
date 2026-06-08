"""Greenhouse Job Board API (public, no auth).

    https://boards-api.greenhouse.io/v1/boards/{token}/jobs
"""
from __future__ import annotations

from .base import Scraper, http_get_json
from ..models import RawPosting


class GreenhouseScraper(Scraper):
    name = "greenhouse"

    def fetch(self, employer: dict) -> list[RawPosting]:
        token = employer["token"]
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        data = http_get_json(url, params={"content": "false"})
        out: list[RawPosting] = []
        for j in data.get("jobs", []):
            loc = (j.get("location") or {}).get("name") or ""
            depts = [d.get("name") for d in j.get("departments", []) if d.get("name")]
            out.append(RawPosting(
                source=self.name,
                employer_id=employer["id"],
                employer_name=employer["name"],
                external_id=str(j.get("id", "")),
                url=j.get("absolute_url", ""),
                raw_title=j.get("title", "").strip(),
                locations=[loc] if loc else [],
                department=", ".join(depts) if depts else None,
                updated_at=j.get("updated_at"),
                raw={"requisition_id": j.get("requisition_id")},
            ))
        return out
