"""SmartRecruiters public posting API (paged).

    https://api.smartrecruiters.com/v1/companies/{token}/postings

NOTE: this endpoint returns HTTP 200 with totalFound=0 for unknown tokens, so
detect_ats requires totalFound>0 before trusting a token.
"""
from __future__ import annotations

from .base import Scraper, http_get_json
from ..models import RawPosting

PAGE = 100


class SmartRecruitersScraper(Scraper):
    name = "smartrecruiters"

    def fetch(self, employer: dict) -> list[RawPosting]:
        token = employer["token"]
        base = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
        out: list[RawPosting] = []
        offset = 0
        while True:
            data = http_get_json(base, params={"limit": PAGE, "offset": offset})
            content = data.get("content", [])
            for j in content:
                loc = j.get("location") or {}
                city = loc.get("city") or ""
                country = loc.get("country") or ""
                locstr = ", ".join([p for p in (city, country) if p])
                dept = (j.get("department") or {}).get("label")
                out.append(RawPosting(
                    source=self.name,
                    employer_id=employer["id"],
                    employer_name=employer["name"],
                    external_id=str(j.get("id") or j.get("refNumber") or ""),
                    url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}",
                    raw_title=(j.get("name") or "").strip(),
                    locations=[locstr] if locstr else [],
                    department=dept,
                    posted_at=j.get("releasedDate"),
                ))
            offset += PAGE
            if offset >= data.get("totalFound", 0) or not content:
                break
        return out
