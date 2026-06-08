"""Resolve a free-text company name (from LinkedIn / eFC) to a watchlist
employer id, so market-wide postings cross-link to the right firm -- and so
`candidate` firms with no ATS still get covered via the query sources.

Unmatched companies become synthetic `ext-*` employers: real market discovery
("don't miss opportunities") without polluting the curated watchlist.
"""
from __future__ import annotations

import functools
import re
import unicodedata

from .config import load_employers

# Hand-curated aliases (normalized form -> watchlist id).
ALIASES = {
    "susquehanna": "sig", "susquehanna international group": "sig", "sig susquehanna": "sig",
    "chicago trading": "ctc", "chicago trading company": "ctc",
    "bam": "balyasny", "balyasny asset management": "balyasny",
    "man": "mangroup", "ahl": "mangroup", "man ahl": "mangroup",
    "jp morgan": "jpmorgan", "jpmorgan chase": "jpmorgan", "j p morgan": "jpmorgan",
    "bofa": "bofa", "bank of america merrill lynch": "bofa", "merrill lynch": "bofa",
    "socgen": "socgen", "sg cib": "socgen", "societe generale cib": "socgen",
    "deutsche bank": "deutschebank", "db": "deutschebank",
    "qube": "qrt", "qube research and technologies": "qrt",
    "de shaw": "deshaw", "d e shaw": "deshaw", "the d e shaw group": "deshaw",
    "hudson river trading": "hrt",
    "two sigma investments": "twosigma",
}


def normalize_name(s: str) -> str:
    s = (s or "").lower().replace("&", " and ")
    # fold accents (société -> societe) for robust FR/DE matching
    s = "".join(c for c in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(c))
    s = re.sub(r"\(.*?\)", " ", s)          # drop qualifiers like "(Markets)"
    s = re.sub(r"[.,/()'`]", " ", s)
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # drop a trailing generic descriptor that LinkedIn often appends
    s = re.sub(r"\b(group|holdings|holding|inc|llc|ltd|limited|plc|llp|sa|ag|"
               r"sas|gmbh|co|company)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_name(s)).strip("-")[:48]


@functools.lru_cache(maxsize=1)
def _index() -> dict:
    by_full: dict[str, dict] = {}
    for e in load_employers():
        by_full[normalize_name(e["name"])] = e
    return by_full


def resolve(company_name: str) -> tuple[str, str, str]:
    """Return (employer_id, employer_name, employer_type)."""
    by_full = _index()
    n = normalize_name(company_name)
    if n in by_full:
        e = by_full[n]
        return e["id"], e["name"], e.get("type", "")
    if n in ALIASES:
        eid = ALIASES[n]
        e = next((x for x in load_employers() if x["id"] == eid), None)
        if e:
            return e["id"], e["name"], e.get("type", "")
    # unknown -> synthetic external employer (market discovery)
    return f"ext-{_slug(company_name)}", company_name.strip(), "OTHER"
