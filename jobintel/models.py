"""Core data model.

Three layers:

  RawPosting  -- one raw annonce as returned by a single source/scraper.
  JobSource   -- a normalized, persisted source row (1 job <-> N sources).
  Job         -- the canonical, de-duplicated offer shown in the frontend.

Everything is plain dataclasses serialized to JSON (git-diffable state).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Raw layer (scraper output)
# --------------------------------------------------------------------------- #
@dataclass
class RawPosting:
    """A single annonce from one source, before normalization/dedup."""
    source: str                      # "greenhouse", "lever", "linkedin", ...
    employer_id: str                 # slug from the watchlist
    employer_name: str
    external_id: str                 # ATS requisition id (strong dedup key)
    url: str                         # canonical apply/listing URL
    raw_title: str
    locations: list[str] = field(default_factory=list)
    department: Optional[str] = None
    updated_at: Optional[str] = None  # ISO8601 if the source provides it
    posted_at: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)  # original payload (audit)

    def source_id(self) -> str:
        """Stable id for this source row: prefer (source+external_id)."""
        basis = f"{self.source}|{self.employer_id}|{self.external_id or self.url}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Persisted source layer
# --------------------------------------------------------------------------- #
@dataclass
class JobSource:
    source_id: str
    job_id: str                      # canonical job this source maps to
    source: str
    employer_id: str
    url: str
    external_id: str
    raw_title: str
    locations: list[str] = field(default_factory=list)
    updated_at: Optional[str] = None
    first_seen: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "JobSource":
        return cls(**d)


# --------------------------------------------------------------------------- #
# Canonical job layer
# --------------------------------------------------------------------------- #
STATUS_OPEN = "open"
STATUS_STALE = "stale"     # not seen this run, within grace period
STATUS_CLOSED = "closed"   # missing beyond grace period


@dataclass
class Job:
    job_id: str
    employer_id: str
    employer_name: str
    employer_type: str               # HF | MM | PROP | QUANT | BANK
    title_raw: str                   # representative raw title
    title_normalized: str
    role_family: str                 # TRADING | QUANT_TRADING | ... | OUT
    seniority: Optional[str]
    asset_classes: list[str]
    in_scope: bool
    scope_reason: str
    locations: list[str]             # union across sources
    is_target_geo: bool              # at least one location in priority/secondary geo
    source_ids: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # source names, e.g. ["greenhouse"]
    status: str = STATUS_OPEN
    content_hash: str = ""
    first_seen: str = ""
    last_seen: str = ""
    last_changed: str = ""
    missing_runs: int = 0            # consecutive runs not seen (drives CLOSED)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        return cls(**d)


def canonical_job_id(employer_id: str, normalized_title: str, role_family: str) -> str:
    """Deterministic canonical key.

    Per product decision: the same requisition opened in several cities is ONE
    multi-city offer -> we key on (employer, normalized_title, role_family) and
    union the locations. Two distinct reqs with an identical title collapse into
    one card (accepted trade-off; sources remain individually listed).
    """
    basis = f"{employer_id}|{normalized_title}|{role_family}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def content_hash(title_normalized: str, locations: list[str], role_family: str,
                 seniority: Optional[str], source_ids: list[str]) -> str:
    """Hash of the meaningful content -> drives MODIFIED detection.

    A new source appearing for the same job, a new city, or a role/seniority
    reclassification all count as a modification.
    """
    payload = "|".join([
        title_normalized,
        ",".join(sorted(set(loc.lower() for loc in locations))),
        role_family,
        seniority or "",
        ",".join(sorted(set(source_ids))),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
