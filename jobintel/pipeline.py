"""Crawl orchestration: scrape -> classify/dedup -> diff -> persist.

Resilience contract:
  * each employer is scraped in isolation; one failure never aborts the crawl
  * CLOSED is only inferred for employers that were crawled successfully this
    run (a scraper error must NOT make jobs look closed)
  * NEW / MODIFIED / CLOSED events are appended to the changelog
  * per-source health is tracked across runs ("source muette depuis N runs")
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from .config import load_employers, load_queries
from .dedup import build_canonical
from .models import RawPosting, STATUS_OPEN, STATUS_STALE, STATUS_CLOSED
from .scrapers import get_scraper, get_query_scraper, QUERY_SOURCE_NAMES
from . import store

log = logging.getLogger("jobintel.pipeline")

GRACE_RUNS = 2            # misses before a job is marked CLOSED (~1 day @ 2x/day)
QUERY_GRACE_RUNS = 6     # larger grace for query-only jobs (ranking is volatile)
PURGE_CLOSED_DAYS = 180   # drop long-closed jobs to bound state size


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scrape_all(employers: list[dict]) -> tuple[list[RawPosting], dict, set[str]]:
    """Return (raw_postings, health_by_employer, crawled_ok_ids)."""
    raws: list[RawPosting] = []
    health: dict[str, dict] = {}
    crawled_ok: set[str] = set()

    for emp in employers:
        ats = emp.get("ats", "unknown")
        scraper = get_scraper(ats) if ats not in (None, "unknown") else None
        if scraper is None or not scraper.configured(emp):
            health[emp["id"]] = {"status": "skipped", "reason": f"ats={ats}", "count": 0}
            continue
        try:
            postings = scraper.fetch(emp)
            raws.extend(postings)
            crawled_ok.add(emp["id"])
            health[emp["id"]] = {"status": "ok", "count": len(postings)}
            log.info("scraped %-20s %-14s -> %d postings", emp["id"], ats, len(postings))
        except Exception as exc:  # noqa: BLE001 - isolate per-source failures
            health[emp["id"]] = {"status": "error", "reason": str(exc)[:160], "count": 0}
            log.error("scrape FAILED %s (%s): %s", emp["id"], ats, exc)
    return raws, health, crawled_ok


def scrape_queries() -> tuple[list[RawPosting], dict, bool]:
    """Run market-wide query sources (LinkedIn/eFC). Best-effort: returns
    (raw_postings, health_by_source, any_source_ran_ok)."""
    cfg = load_queries()
    keywords = cfg.get("keywords", [])
    locations = cfg.get("locations", [])
    raws: list[RawPosting] = []
    health: dict[str, dict] = {}
    any_ok = False

    for sname, sconf in cfg.get("sources", {}).items():
        if not sconf.get("enabled"):
            continue
        scraper = get_query_scraper(sname)
        if scraper is None:
            continue
        count, errors = 0, 0
        for kw in keywords:
            for loc in locations:
                try:
                    res = scraper.search(kw, loc)
                    raws.extend(res)
                    count += len(res)
                except Exception as exc:  # noqa: BLE001 - isolate per query
                    errors += 1
                    log.warning("query %s '%s'@%s failed: %s", sname, kw, loc, exc)
        ran_ok = count > 0
        any_ok = any_ok or ran_ok
        health[sname] = {"status": "ok" if ran_ok else ("error" if errors else "empty"),
                         "count": count, "errors": errors}
        log.info("query source %-18s -> %d postings (%d errors)", sname, count, errors)
    return raws, health, any_ok


def run_crawl() -> dict:
    now = _now()
    employers = load_employers()
    emp_type = {e["id"]: e.get("type", "") for e in employers}

    prev_jobs = store.load_jobs()
    prev_sources = store.load_sources()
    prev_meta = store._read_json(store.META_FILE, {})
    prev_health = prev_meta.get("source_health", {})

    raws, health, crawled_ok = scrape_all(employers)
    q_raws, q_health, query_ran_ok = scrape_queries()
    raws = raws + q_raws
    health.update(q_health)
    new_jobs, new_sources = build_canonical(raws, emp_type, now)

    events: list[dict] = []

    # ---- merge sources (preserve first_seen) ----
    merged_sources = dict(prev_sources)
    for sid, s in new_sources.items():
        if sid in merged_sources:
            s.first_seen = merged_sources[sid].first_seen
        merged_sources[sid] = s

    # ---- merge jobs: NEW / MODIFIED ----
    merged_jobs = dict(prev_jobs)
    for jid, j in new_jobs.items():
        old = prev_jobs.get(jid)
        if old is None:
            j.first_seen = now
            j.last_changed = now
            merged_jobs[jid] = j
            if j.in_scope:
                events.append(_event("NEW", now, j))
        else:
            j.first_seen = old.first_seen
            j.missing_runs = 0
            j.status = STATUS_OPEN
            if j.content_hash != old.content_hash:
                j.last_changed = now
                merged_jobs[jid] = j
                if j.in_scope:
                    events.append(_event("MODIFIED", now, j,
                                         extra={"old_hash": old.content_hash}))
            else:
                # unchanged: refresh last_seen only
                old.last_seen = now
                old.missing_runs = 0
                old.status = STATUS_OPEN
                merged_jobs[jid] = old

    # ---- absent jobs: STALE -> CLOSED ----
    # ATS-backed jobs close after GRACE_RUNS. Query-only jobs (LinkedIn/eFC),
    # whose ranking is volatile, only close after the larger QUERY_GRACE_RUNS,
    # and only when a query source actually ran this turn. Jobs whose source
    # wasn't crawled at all are left untouched (cannot conclude closure).
    seen_now = set(new_jobs)
    for jid, j in list(merged_jobs.items()):
        if jid in seen_now:
            continue
        query_only = bool(j.sources) and set(j.sources) <= QUERY_SOURCE_NAMES
        if j.employer_id in crawled_ok:
            grace = GRACE_RUNS
        elif query_ran_ok and query_only:
            grace = QUERY_GRACE_RUNS
        else:
            continue  # cannot conclude closure if its source wasn't crawled
        j.missing_runs += 1
        if j.missing_runs >= grace and j.status != STATUS_CLOSED:
            j.status = STATUS_CLOSED
            j.last_changed = now
            if j.in_scope:
                events.append(_event("CLOSED", now, j))
        elif j.status != STATUS_CLOSED:
            j.status = STATUS_STALE

    # ---- purge long-closed jobs to bound size ----
    cutoff = datetime.now(timezone.utc) - timedelta(days=PURGE_CLOSED_DAYS)
    purged = 0
    for jid, j in list(merged_jobs.items()):
        if j.status == STATUS_CLOSED and _parse(j.last_seen) < cutoff:
            for sid in j.source_ids:
                merged_sources.pop(sid, None)
            del merged_jobs[jid]
            purged += 1

    # ---- source health w/ consecutive-failure tracking ----
    for emp_id, h in health.items():
        prev = prev_health.get(emp_id, {})
        if h["status"] == "ok":
            h["consecutive_failures"] = 0
            h["last_ok"] = now
        elif h["status"] == "error":
            h["consecutive_failures"] = prev.get("consecutive_failures", 0) + 1
            h["last_ok"] = prev.get("last_ok")
        else:  # skipped
            h["consecutive_failures"] = prev.get("consecutive_failures", 0)
            h["last_ok"] = prev.get("last_ok")

    # ---- persist ----
    store.save_jobs(merged_jobs)
    store.save_sources(merged_sources)
    store.append_changes(events)

    in_scope_open = [j for j in merged_jobs.values()
                     if j.in_scope and j.status in (STATUS_OPEN, STATUS_STALE)]
    meta = {
        "last_run": now,
        "counts": {
            "employers_total": len(employers),
            "employers_crawled_ok": len(crawled_ok),
            "raw_postings": len(raws),
            "jobs_total": len(merged_jobs),
            "jobs_in_scope_open": len(in_scope_open),
            "purged": purged,
        },
        "events_this_run": _summarize_events(events),
        "source_health": health,
    }
    store.save_meta(meta)
    log.info("run complete: %s", meta["counts"])
    log.info("events: %s", meta["events_this_run"])
    return meta


def _event(kind: str, ts: str, job, extra: dict | None = None) -> dict:
    ev = {
        "ts": ts, "kind": kind, "job_id": job.job_id,
        "employer_id": job.employer_id, "employer_name": job.employer_name,
        "title": job.title_raw, "role_family": job.role_family,
        "locations": job.locations, "sources": job.sources,
    }
    if extra:
        ev.update(extra)
    return ev


def _summarize_events(events: list[dict]) -> dict:
    out: dict[str, int] = {}
    for e in events:
        out[e["kind"]] = out.get(e["kind"], 0) + 1
    return out


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc)
