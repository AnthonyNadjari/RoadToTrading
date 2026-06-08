"""Build the static frontend feed (web/data/*.json) from canonical state.

The frontend is a static SPA: it loads these JSON files and does all
search/filtering client-side (0-budget, no backend).
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import WEB_DATA_DIR, load_employers
from . import store
from .store import _read_json, CHANGELOG_FILE

RECENT_CHANGES = 500


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))


def build_frontend() -> dict:
    jobs = store.load_jobs()
    sources = store.load_sources()
    meta = _read_json(store.META_FILE, {})

    job_feed = []
    for j in jobs.values():
        if not j.in_scope:
            continue
        srcs = []
        for sid in j.source_ids:
            s = sources.get(sid)
            if not s:
                continue
            srcs.append({"source": s.source, "url": s.url,
                         "external_id": s.external_id, "locations": s.locations})
        job_feed.append({
            "id": j.job_id,
            "employer": j.employer_name,
            "employer_id": j.employer_id,
            "employer_type": j.employer_type,
            "title": j.title_raw,
            "role": j.role_family,
            "seniority": j.seniority,
            "assets": j.asset_classes,
            "locations": j.locations,
            "target_geo": j.is_target_geo,
            "status": j.status,
            "sources": sorted({s["source"] for s in srcs}),
            "source_links": srcs,
            "first_seen": j.first_seen,
            "last_seen": j.last_seen,
            "last_changed": j.last_changed,
        })
    job_feed.sort(key=lambda d: d["last_changed"], reverse=True)

    # recent change events (tail of changelog)
    changes = []
    if CHANGELOG_FILE.exists():
        with open(CHANGELOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()[-RECENT_CHANGES:]
        changes = [json.loads(l) for l in lines]
        changes.reverse()

    employers = load_employers()
    health = meta.get("source_health", {})
    emp_summary = []
    for e in employers:
        h = health.get(e["id"], {})
        emp_summary.append({
            "id": e["id"], "name": e["name"], "type": e["type"],
            "tier": e.get("tier"), "ats": e.get("ats", "unknown"),
            "status": e.get("status"), "careers_url": e.get("careers_url"),
            "health": h.get("status", "unknown"),
            "count": h.get("count", 0),
            "consecutive_failures": h.get("consecutive_failures", 0),
        })

    _write(WEB_DATA_DIR / "jobs.json", job_feed)
    _write(WEB_DATA_DIR / "changes.json", changes)
    _write(WEB_DATA_DIR / "meta.json", {
        "generated_at": meta.get("last_run"),
        "counts": meta.get("counts", {}),
        "events_last_run": meta.get("events_this_run", {}),
        "employers": emp_summary,
    })
    return {"jobs": len(job_feed), "changes": len(changes), "employers": len(emp_summary)}
