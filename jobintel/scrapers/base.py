"""Scraper base class + shared resilient HTTP helpers.

Design goals (0-budget, runs on shared GitHub Actions IPs):
  * polite: identifiable UA, timeouts, bounded retries with backoff
  * isolated: a failing source must NEVER crash the whole crawl
  * deterministic: every scraper returns a list[RawPosting]
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests

from ..models import RawPosting

log = logging.getLogger("jobintel.scraper")

USER_AGENT = (
    "Mozilla/5.0 (compatible; RoadToTrading-JobIntel/0.1; "
    "+https://github.com/AnthonyNadjari/RoadToTrading)"
)
# Query sources (LinkedIn/eFC) serve guest HTML only to browser-like clients.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
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


def urllib_get_text(url: str, *, params: Optional[dict] = None,
                    headers: Optional[dict] = None,
                    timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fetch text via stdlib urllib (different client fingerprint than
    `requests`). Some anti-bot front-ends (e.g. eFinancialCareers) serve a fake
    'maintenance' stub to `requests` but answer urllib -- best-effort fallback.
    Same fail-fast-on-4xx / retry-on-5xx policy as http_get."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    merged = {"User-Agent": BROWSER_UA, "Accept": "text/html"}
    if headers:
        merged.update(headers)
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=merged)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS:
                raise SourceError(f"GET {url} -> HTTP {exc.code}")
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
        if attempt < MAX_RETRIES - 1:
            time.sleep(BACKOFF_BASE ** (attempt + 1))
    raise SourceError(f"GET {url} failed after {MAX_RETRIES} tries: {last_exc}")


class Scraper(ABC):
    """One scraper per ATS provider. Stateless; instantiated per crawl."""

    name: str = "base"

    def configured(self, employer: dict) -> bool:
        """Whether this employer has enough config for this scraper to run.
        Default: a board token is present."""
        return bool(employer.get("token"))

    @abstractmethod
    def fetch(self, employer: dict) -> list[RawPosting]:
        """Return all current postings for one employer. Must not raise for
        empty boards; raise SourceError only on real fetch failures."""
        raise NotImplementedError


class QueryScraper(ABC):
    """A query-based (market-wide) source such as LinkedIn or eFinancialCareers.

    Unlike Scraper (employer-centric), these search by (keyword, location) and
    discover postings across the whole market, including firms not on the
    watchlist. Their results feed NEW/MODIFIED detection and cross-source
    linking, but never drive CLOSED inference on their own (best-effort, noisy)."""

    name: str = "query-base"

    @abstractmethod
    def search(self, keyword: str, location: str) -> list[RawPosting]:
        raise NotImplementedError


def http_post_json(url: str, body: dict, *, headers: Optional[dict] = None,
                   timeout: int = DEFAULT_TIMEOUT) -> Any:
    """POST JSON with the same retry policy as http_get."""
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json",
              "Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=body, headers=merged, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
        else:
            if resp.ok:
                return resp.json()
            if resp.status_code not in RETRYABLE_STATUS:
                raise SourceError(f"POST {url} -> HTTP {resp.status_code}")
            last_exc = SourceError(f"HTTP {resp.status_code}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(BACKOFF_BASE ** (attempt + 1))
    raise SourceError(f"POST {url} failed after {MAX_RETRIES} tries: {last_exc}")
