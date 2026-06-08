"""LinkedIn Jobs — guest (unauthenticated) search endpoint. BEST-EFFORT.

    https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
        ?keywords=...&location=...&start=0

Returns an HTML fragment of job cards. This violates LinkedIn ToS and is
rate-limited / may be blocked from datacenter IPs -> treated as best-effort:
failures are isolated and never drive CLOSED inference. Discovered companies
are resolved against the watchlist (cross-source linking) or kept as `ext-*`.
"""
from __future__ import annotations

import html as H
import re
import time

from .base import QueryScraper, http_get, BROWSER_UA, SourceError
from ..models import RawPosting
from ..employers_index import resolve

MAX_PAGES = 4
PAGE_STEP = 25
PAGE_DELAY = 1.0

_TITLE = re.compile(r'base-search-card__title">\s*(.*?)\s*</h3>', re.S)
_COMPANY = re.compile(r'base-search-card__subtitle">\s*(.*?)\s*</h4>', re.S)
_LOC = re.compile(r'job-search-card__location">\s*(.*?)\s*</span>', re.S)
_LINK = re.compile(r'href="(https://[a-z.]*linkedin\.com/jobs/view/[^"?]+)')
_URN = re.compile(r'urn:li:jobPosting:(\d+)')
_TAGS = re.compile(r'<[^>]+>')


def _clean(s: str) -> str:
    return H.unescape(_TAGS.sub("", s)).strip()


class LinkedInScraper(QueryScraper):
    name = "linkedin"

    def search(self, keyword: str, location: str) -> list[RawPosting]:
        url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        out: list[RawPosting] = []
        for page in range(MAX_PAGES):
            params = {"keywords": keyword, "location": location,
                      "start": page * PAGE_STEP}
            try:
                resp = http_get(url, params=params,
                                headers={"User-Agent": BROWSER_UA, "Accept": "text/html"})
            except SourceError:
                break  # blocked / rate-limited: stop paginating, keep what we have
            cards = resp.text.split("</li>")
            found = 0
            for c in cards:
                link = _LINK.search(c)
                title = _TITLE.search(c)
                if not link or not title:
                    continue
                urn = _URN.search(c)
                ext_id = urn.group(1) if urn else (
                    re.search(r"-(\d{6,})$", link.group(1)) or [None, link.group(1)])[1]
                company = _clean(_COMPANY.search(c).group(1)) if _COMPANY.search(c) else ""
                loc = _clean(_LOC.search(c).group(1)) if _LOC.search(c) else location
                emp_id, emp_name, _ = resolve(company)
                out.append(RawPosting(
                    source=self.name, employer_id=emp_id, employer_name=emp_name,
                    external_id=str(ext_id), url=link.group(1),
                    raw_title=_clean(title.group(1)),
                    locations=[loc] if loc else [],
                ))
                found += 1
            if found < 3:
                break
            time.sleep(PAGE_DELAY)
        return out
