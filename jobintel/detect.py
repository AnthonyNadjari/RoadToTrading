"""ATS auto-detection for employers with `ats: unknown`.

For each candidate employer we generate plausible board tokens from its name and
probe every supported provider. A hit is only accepted when the endpoint returns
at least one REAL job (guards against Workable/SmartRecruiters false positives
that answer 200 with an empty/placeholder account).

Output is written to data/ats_detection.json for review; applying it to
employers.yaml is a deliberate (human/Claude) step to keep the curated config
clean.
"""
from __future__ import annotations

import json
import logging
import re

from .config import DATA_DIR, load_employers
from .scrapers.base import http_get_json, SourceError

log = logging.getLogger("jobintel.detect")

_STOP = {"capital", "trading", "markets", "market", "group", "securities",
         "management", "investment", "investments", "partners", "associates",
         "fund", "funds", "co", "llc", "ltd", "the", "global", "asset"}


def candidate_tokens(employer: dict) -> list[str]:
    name = employer["name"].lower()
    name = re.sub(r"\(.*?\)", " ", name)              # drop parentheticals
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    words = [w for w in name.split() if w]
    core = [w for w in words if w not in _STOP] or words
    cands = {
        employer["id"],
        "".join(words),
        "".join(core),
        "-".join(core),
        core[0] if core else "",
    }
    return [c for c in cands if len(c) >= 3]


def _probe(provider: str, token: str):
    """Return (count, sample_title) if a real board is found, else None."""
    try:
        if provider == "greenhouse":
            d = http_get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false")
            jobs = d.get("jobs", [])
            return (len(jobs), jobs[0]["title"]) if jobs else None
        if provider == "lever":
            d = http_get_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
            return (len(d), d[0].get("text")) if d else None
        if provider == "ashby":
            d = http_get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
            jobs = d.get("jobs", [])
            return (len(jobs), jobs[0].get("title")) if jobs else None
        if provider == "recruitee":
            d = http_get_json(f"https://{token}.recruitee.com/api/offers/")
            offers = d.get("offers", [])
            return (len(offers), offers[0].get("title")) if offers else None
        if provider == "smartrecruiters":
            d = http_get_json(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=1")
            n = d.get("totalFound", 0)
            content = d.get("content", [])
            return (n, content[0].get("name")) if n and content else None
        if provider == "workable":
            d = http_get_json(f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true")
            jobs = d.get("jobs", [])
            return (len(jobs), jobs[0].get("title")) if jobs else None
    except SourceError:
        return None
    except Exception:  # noqa: BLE001
        return None
    return None


PROVIDERS = ["greenhouse", "lever", "ashby", "recruitee", "smartrecruiters", "workable"]


def detect_all() -> list[dict]:
    results = []
    for emp in load_employers():
        if emp.get("ats") not in (None, "unknown"):
            continue
        for token in candidate_tokens(emp):
            for provider in PROVIDERS:
                hit = _probe(provider, token)
                if hit:
                    count, sample = hit
                    results.append({
                        "employer_id": emp["id"], "name": emp["name"],
                        "ats": provider, "token": token,
                        "count": count, "sample_title": sample,
                    })
                    log.info("DETECTED %s -> %s/%s (%d jobs) e.g. %s",
                             emp["id"], provider, token, count, sample)
    out = DATA_DIR / "ats_detection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    return results
