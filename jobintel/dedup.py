"""Multi-source de-duplication.

Strategy (deterministic):
  * Within an employer, a canonical job is keyed by
    (employer_id, normalized_title, role_family)  -> canonical_job_id.
  * The same requisition posted in several cities collapses into ONE job whose
    `locations` is the union across all its source annonces (product decision:
    "1 multi-city offer").
  * Each raw annonce becomes a JobSource row linked to that job, so a job seen
    on Greenhouse AND LinkedIn shows both sources under one card.
  * Anonymized recruiter posts (no resolvable employer) are intentionally NOT
    fuzzy-linked here; they stay separate to avoid false merges.

This module is pure: it turns a list[RawPosting] into (jobs, sources) given the
classification of each posting. Diffing against previous state lives in
pipeline.py.
"""
from __future__ import annotations

from .classify import classify, is_target_geo
from .models import (Job, JobSource, RawPosting, canonical_job_id, content_hash,
                     STATUS_OPEN)
from .normalize import normalize_title


def _coerce_locations(locs) -> list[str]:
    """Defensive: a source must never crash the crawl by returning non-string
    locations. Map dicts to their label/city/name; stringify anything else."""
    out: list[str] = []
    for x in locs or []:
        if isinstance(x, str):
            s = x
        elif isinstance(x, dict):
            s = x.get("label") or x.get("city") or x.get("name") or ""
        else:
            s = str(x)
        if s:
            out.append(s)
    return out


def build_canonical(raws: list[RawPosting], employer_type_by_id: dict[str, str],
                    now: str) -> tuple[dict[str, Job], dict[str, JobSource]]:
    jobs: dict[str, Job] = {}
    sources: dict[str, JobSource] = {}
    # group source-ids per job to compute content hash deterministically
    job_source_ids: dict[str, list[str]] = {}

    for r in raws:
        norm = normalize_title(r.raw_title)
        if not norm:
            continue
        etype = employer_type_by_id.get(r.employer_id) or (
            "OTHER" if r.employer_id.startswith("ext-") else "")
        cls = classify(norm, r.department, etype)
        jid = canonical_job_id(r.employer_id, norm, cls.role_family)
        sid = r.source_id()
        locs = _coerce_locations(r.locations)

        # --- source row ---
        sources[sid] = JobSource(
            source_id=sid, job_id=jid, source=r.source, employer_id=r.employer_id,
            url=r.url, external_id=r.external_id, raw_title=r.raw_title,
            locations=locs, updated_at=r.updated_at,
            first_seen=now, last_seen=now,
        )
        job_source_ids.setdefault(jid, []).append(sid)

        # --- canonical job (create or merge) ---
        if jid not in jobs:
            jobs[jid] = Job(
                job_id=jid, employer_id=r.employer_id, employer_name=r.employer_name,
                employer_type=etype, title_raw=r.raw_title, title_normalized=norm,
                role_family=cls.role_family, seniority=cls.seniority,
                asset_classes=list(cls.asset_classes), in_scope=cls.in_scope,
                scope_reason=cls.scope_reason, locations=list(locs),
                is_target_geo=is_target_geo(locs),
                source_ids=[], sources=[], status=STATUS_OPEN,
                first_seen=now, last_seen=now, last_changed=now,
            )
        else:
            j = jobs[jid]
            # union locations, asset classes, sources
            for loc in locs:
                if loc not in j.locations:
                    j.locations.append(loc)
            for ac in cls.asset_classes:
                if ac not in j.asset_classes:
                    j.asset_classes.append(ac)
            j.is_target_geo = j.is_target_geo or is_target_geo(locs)

    # finalize source links + content hash
    for jid, j in jobs.items():
        sids = sorted(set(job_source_ids.get(jid, [])))
        j.source_ids = sids
        j.sources = sorted({sources[s].source for s in sids})
        j.content_hash = content_hash(j.title_normalized, j.locations,
                                      j.role_family, j.seniority, sids)
    return jobs, sources
