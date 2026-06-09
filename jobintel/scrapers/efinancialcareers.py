"""eFinancialCareers — public job search. BEST-EFFORT.

    https://www.efinancialcareers.com/jobs?q=<kw>&location=<loc>

The search page embeds full job objects as JSON (nested), which we extract by
brace-matching around each `"companyName"` token. Same best-effort contract as
LinkedIn: isolated failures, never drives CLOSED, companies resolved against the
watchlist or kept as `ext-*`.
"""
from __future__ import annotations

import json
import re

from .base import QueryScraper, urllib_get_text, SourceError
from ..models import RawPosting
from ..employers_index import resolve

_ANCHOR = '"companyName"'


def _extract_objects(s: str) -> list[dict]:
    """Pull each JSON object that contains a companyName, via brace matching."""
    objs, seen = [], set()
    for m in re.finditer(re.escape(_ANCHOR), s):
        # back-scan to the enclosing '{'
        depth, start, i = 0, None, m.start()
        while i >= 0:
            ch = s[i]
            if ch == "}":
                depth += 1
            elif ch == "{":
                if depth == 0:
                    start = i
                    break
                depth -= 1
            i -= 1
        if start is None or start in seen:
            continue
        seen.add(start)
        # forward-scan to the matching '}'
        depth, j = 0, start
        while j < len(s):
            ch = s[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            objs.append(json.loads(s[start:j + 1]))
        except Exception:
            pass
    return objs


class EfcScraper(QueryScraper):
    name = "efinancialcareers"

    def search(self, keyword: str, location: str) -> list[RawPosting]:
        url = "https://www.efinancialcareers.com/jobs"
        try:
            text = urllib_get_text(url, params={"q": keyword, "location": location})
        except SourceError:
            return []
        out: list[RawPosting] = []
        for o in _extract_objects(text):
            title = (o.get("title") or "").strip()
            if not title:
                continue
            company = o.get("fullCompanyName") or o.get("companyName") or ""
            emp_id, emp_name, _ = resolve(company)
            locobj = o.get("location") if isinstance(o.get("location"), dict) else {}
            loc = o.get("jobLocation")
            if not isinstance(loc, str) or not loc:
                loc = locobj.get("label") or locobj.get("city") or location
            ext_id = str(o.get("jobId") or o.get("id") or "")
            href = o.get("detailsPageUrl") or ""
            if href and href.startswith("/"):
                href = "https://www.efinancialcareers.com" + href
            out.append(RawPosting(
                source=self.name, employer_id=emp_id, employer_name=emp_name,
                external_id=ext_id, url=href, raw_title=title,
                locations=[loc] if loc else [], posted_at=o.get("postedDate"),
            ))
        return out
