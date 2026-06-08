"""Workday CXS API scraper (config-driven, no auth).

Workday career sites expose a JSON endpoint:
    POST https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
         body: {"limit":20,"offset":0,"searchText":"","appliedFacets":{}}
         -> {"total":N, "jobPostings":[{title, externalPath, locationsText, ...}]}

Employer config (in employers.yaml):
    ats: workday
    workday: {tenant: barclays, host: wd3, site: External_Career_Site_Barclays}

We page through everything (limit capped at 20 server-side) and let the
classifier filter to in-scope roles -- Workday's own search is too fuzzy to
trust for precision.
"""
from __future__ import annotations

import re
import time

from .base import Scraper, http_post_json
from ..models import RawPosting

PAGE = 20
MAX_PAGES = 120          # safety cap (~2400 postings/employer)
PAGE_DELAY = 0.3         # politeness between pages
_REQ = re.compile(r"((?:JR|R|REQ)[-_]?\d{3,}|\d{6,})", re.IGNORECASE)


class WorkdayScraper(Scraper):
    name = "workday"

    def configured(self, employer: dict) -> bool:
        w = employer.get("workday") or {}
        return all(w.get(k) for k in ("tenant", "host", "site"))

    def fetch(self, employer: dict) -> list[RawPosting]:
        w = employer["workday"]
        tenant, host, site = w["tenant"], w["host"], w["site"]
        root = f"https://{tenant}.{host}.myworkdayjobs.com"
        api = f"{root}/wday/cxs/{tenant}/{site}/jobs"
        out: list[RawPosting] = []
        offset = 0
        for _ in range(MAX_PAGES):
            data = http_post_json(api, {"limit": PAGE, "offset": offset,
                                        "searchText": "", "appliedFacets": {}})
            postings = data.get("jobPostings", [])
            for j in postings:
                ext_path = j.get("externalPath", "")
                m = _REQ.search(ext_path)
                ext_id = m.group(1) if m else ext_path
                loc = j.get("locationsText") or ""
                out.append(RawPosting(
                    source=self.name,
                    employer_id=employer["id"],
                    employer_name=employer["name"],
                    external_id=str(ext_id),
                    url=f"{root}/{site}{ext_path}",
                    raw_title=(j.get("title") or "").strip(),
                    locations=[loc] if loc else [],
                    posted_at=j.get("postedOn"),
                ))
            offset += PAGE
            if offset >= data.get("total", 0) or not postings:
                break
            time.sleep(PAGE_DELAY)
        return out
