"""Ashby public job-board posting API.

    https://api.ashbyhq.com/posting-api/job-board/{token}
"""
from __future__ import annotations

from .base import Scraper, http_get_json
from ..models import RawPosting


class AshbyScraper(Scraper):
    name = "ashby"

    def fetch(self, employer: dict) -> list[RawPosting]:
        token = employer["token"]
        url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        data = http_get_json(url, params={"includeCompensation": "false"})
        out: list[RawPosting] = []
        for j in data.get("jobs", []):
            locs = [j.get("location")] if j.get("location") else []
            for sec in j.get("secondaryLocations") or []:
                loc = sec.get("location") if isinstance(sec, dict) else sec
                if loc:
                    locs.append(loc)
            out.append(RawPosting(
                source=self.name,
                employer_id=employer["id"],
                employer_name=employer["name"],
                external_id=str(j.get("id", "")),
                url=j.get("jobUrl") or j.get("applyUrl", ""),
                raw_title=(j.get("title") or "").strip(),
                locations=list(dict.fromkeys(locs)),
                department=j.get("department") or j.get("team"),
                updated_at=j.get("updatedAt") or j.get("publishedAt"),
            ))
        return out
