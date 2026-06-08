"""Scraper base class + shared resilient HTTP helpers.

Design goals (0-budget, runs on shared GitHub Actions IPs):
  * polite: identifiable UA, timeouts, bounded retries with backoff
  * isolated: a failing source must NEVER crash the whole crawl
  * deterministic: every scraper returns a list[RawPosting]
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests

from ..models import RawPosting

log = logging.getLogger("jobintel.scraper")

USER_AGENT = (
    "Mozilla/5.0 (compatible; RoadToTrading-JobIntel/0.1; "
    "+https://github.com/AnthonyNadjari/RoadToTrading)"
)
DEFAULT_TIMEOUT = 20
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # seconds: 2, 4, 8


class SourceError(Exception):
    """Raised when a source cannot be fetched after retries."""


RETRYABLE_STATUS = (429, 500, 502, 503, 504)


def http_get(url: str, *, params: Optional[dict] = None,
             headers: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    """GET with retries + exponential backoff.

    Retries only on transient conditions (network errors, timeouts, 429, 5xx).
    Other 4xx (e.g. 404 for a non-existent board) are definitive and raise
    immediately -- critical so ATS detection doesn't hang on expected misses.
    """
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, headers=merged, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
        else:
            if resp.ok:
                return resp
            if resp.status_code not in RETRYABLE_STATUS:
                raise SourceError(f"GET {url} -> HTTP {resp.status_code}")
            last_exc = SourceError(f"HTTP {resp.status_code}")
        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_BASE ** (attempt + 1)
            log.warning("GET %s transient (%s); retry in %.0fs", url, last_exc, wait)
            time.sleep(wait)
    raise SourceError(f"GET {url} failed after {MAX_RETRIES} tries: {last_exc}")


def http_get_json(url: str, **kw: Any) -> Any:
    return http_get(url, **kw).json()


class Scraper(ABC):
    """One scraper per ATS provider. Stateless; instantiated per crawl."""

    name: str = "base"

    @abstractmethod
    def fetch(self, employer: dict) -> list[RawPosting]:
        """Return all current postings for one employer. Must not raise for
        empty boards; raise SourceError only on real fetch failures."""
        raise NotImplementedError
