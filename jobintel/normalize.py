"""Title normalization.

Produces a clean, comparable title used both for matching (classification) and
for the canonical dedup key. Conservative: we strip noise, not meaning.
"""
from __future__ import annotations

import re

# gender/diversity markers: (m/f/d) (f/m/x) (w/m/d) h/f ...
_GENDER = re.compile(r"\(?\b[mfwhx](?:[/\\-][mfwhxd]){1,2}\b\)?", re.IGNORECASE)
# trailing " - London", " | Paris", " (Geneva)" style location suffixes
_LOC_SUFFIX = re.compile(r"\s*[\-–|/(]\s*(remote|hybrid|on-?site)\b.*$", re.IGNORECASE)
# requisition / code tokens like "REQ-12345", "(R0012345)", "JR0098765"
_REQ = re.compile(r"\b(req|jr|r|id)[-_ ]?\d{3,}\b", re.IGNORECASE)
_MULTISPACE = re.compile(r"\s+")
_PUNCT_EDGES = re.compile(r"^[\s\-–|,/]+|[\s\-–|,/]+$")


def normalize_title(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    t = _GENDER.sub(" ", t)
    t = _REQ.sub(" ", t)
    t = _LOC_SUFFIX.sub(" ", t)
    t = t.replace("’", "'").replace("–", "-")
    t = _MULTISPACE.sub(" ", t)
    t = _PUNCT_EDGES.sub("", t)
    return t.strip().lower()


def match_text(normalized_title: str, department: str | None) -> str:
    """Text used for keyword matching: title + department, lowercased, padded
    with spaces so whole-word patterns like ' pm ' and 'qr ' match at edges."""
    dept = (department or "").lower()
    return f" {normalized_title} {dept} ".replace("  ", " ")
