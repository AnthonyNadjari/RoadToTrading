"""Persistence layer.

Canonical state is stored as **git-diffable JSON** (no binary DB) so that the
full history lives for free in git, and GitHub Actions can rebuild everything
from the committed files each run. Writes are atomic + key-sorted for clean,
minimal diffs.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .config import STATE_DIR, DATA_DIR
from .models import Job, JobSource

JOBS_FILE = STATE_DIR / "jobs.json"
SOURCES_FILE = STATE_DIR / "sources.json"
META_FILE = STATE_DIR / "meta.json"
CHANGELOG_FILE = DATA_DIR / "changelog.ndjson"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_jobs() -> dict[str, Job]:
    return {d["job_id"]: Job.from_dict(d) for d in _read_json(JOBS_FILE, [])}


def load_sources() -> dict[str, JobSource]:
    return {d["source_id"]: JobSource.from_dict(d) for d in _read_json(SOURCES_FILE, [])}


def save_jobs(jobs: dict[str, Job]) -> None:
    data = [jobs[k].to_dict() for k in sorted(jobs)]
    _atomic_write(JOBS_FILE, json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def save_sources(sources: dict[str, JobSource]) -> None:
    data = [sources[k].to_dict() for k in sorted(sources)]
    _atomic_write(SOURCES_FILE, json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def save_meta(meta: dict) -> None:
    _atomic_write(META_FILE, json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True))


def append_changes(events: list[dict]) -> None:
    if not events:
        return
    CHANGELOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANGELOG_FILE, "a", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")
