"""Deterministic, rule-based classification (no LLM at runtime).

Given a normalized title + department + employer type, decide:
  * role_family  (TRADING / QUANT_TRADING / QUANT_RESEARCH / STRUCTURING /
                  STRATS / QUANT_DEV / OUT / UNCLASSIFIED)
  * in_scope     (bool) + scope_reason
  * seniority
  * asset_classes (multi-label)

The narrow, standardized vocabulary of this niche makes rules accurate enough;
an LLM pass can be layered on later for borderline titles without changing the
schema.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import load_taxonomy
from .normalize import match_text


@dataclass
class Classification:
    role_family: str
    role_label: str
    in_scope: bool
    scope_reason: str
    seniority: str | None
    asset_classes: list[str]


# Engineering/infra markers. A title carrying one of these is routed to
# QUANT_DEV (secondary) at most, never into the priority TRADING/QR/STRATS
# buckets -- keeps "Software Engineer | Trading Team" out of the trading view.
_ENG_MARKERS = (
    "software engineer", "software developer", "developer", "sre",
    "site reliability", "reliability engineer", "network engineer", "devops",
    "data engineer", "platform engineer", "infrastructure engineer",
    "systems engineer", "cloud engineer", "security engineer", "qa engineer",
    "frontend", "back end", "backend", "full stack", "full-stack", "desktop",
    "asic", "fpga", "hardware engineer", "support engineer", "helpdesk",
    "applications specialist", "application specialist",
)


def _is_engineering(text: str) -> bool:
    return any(m in text for m in _ENG_MARKERS)


def _term_matches(term: str, text: str) -> bool:
    """Whole-word match when the term is alphanumeric, else plain substring
    (handles 'm&a', 'c++', 'low-latency')."""
    if re.fullmatch(r"[a-z0-9 ]+", term):
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return term in text


def classify(normalized_title: str, department: str | None,
             employer_type: str) -> Classification:
    tax = load_taxonomy()
    text = match_text(normalized_title, department)

    # 1. hard exclusions win
    for term in tax.get("exclude", []):
        if _term_matches(term.lower(), text):
            return Classification("OUT", "Out of scope", False,
                                  f"excluded:{term}", None, [])

    # 2. score role families.
    #    Specificity-weighted: a multi-word keyword ("quantitative trader")
    #    outweighs a generic one ("trader"), so "Quantitative Trader" lands in
    #    QUANT_TRADING rather than being absorbed by TRADING. Ties break on the
    #    configured business priority.
    #    Engineering titles are constrained to QUANT_DEV only.
    roles = tax["roles"]
    eligible = {"QUANT_DEV"} if _is_engineering(text) else set(roles)
    best_family, best_score, best_priority = None, 0, 999
    for fam, spec in roles.items():
        if fam not in eligible:
            continue
        score = sum(len(kw.split()) for kw in spec["keywords"]
                    if _term_matches(kw.lower(), text))
        if score == 0:
            continue
        prio = spec.get("priority", 99)
        if score > best_score or (score == best_score and prio < best_priority):
            best_family, best_score, best_priority = fam, score, prio

    if best_family is None:
        return Classification("UNCLASSIFIED", "Unclassified", False,
                              "no_role_match", _seniority(text, tax),
                              _assets(text, tax))

    # 2b. QUANT_DEV is secondary: at a bank, require explicit quant/trading
    #     context to avoid pulling in generic software roles.
    if best_family == "QUANT_DEV" and employer_type == "BANK":
        if not any(w in text for w in ("quant", "trading", "trader", "low latency",
                                       "low-latency", "exotic", "pricing")):
            return Classification("OUT", "Out of scope", False,
                                  "quant_dev_bank_no_context", None, [])

    label = roles[best_family]["label"]
    return Classification(best_family, label, True, "matched",
                          _seniority(text, tax), _assets(text, tax))


def _seniority(text: str, tax: dict) -> str | None:
    for level, terms in tax.get("seniority", {}).items():
        if any(_term_matches(t.lower(), text) for t in terms):
            return level
    return None


def _assets(text: str, tax: dict) -> list[str]:
    found = []
    for cls, terms in tax.get("asset_classes", {}).items():
        if any(_term_matches(t.lower(), text) for t in terms):
            found.append(cls)
    return found


def is_target_geo(locations: list[str]) -> bool:
    tax = load_taxonomy()
    geo = tax.get("geo", {})
    targets = [g.lower() for g in (geo.get("priority", []) + geo.get("secondary", []))]
    blob = " ".join(locations).lower()
    return any(city in blob for city in targets)
