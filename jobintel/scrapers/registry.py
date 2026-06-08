"""Maps an ATS name -> scraper instance, and lists detectable providers."""
from __future__ import annotations

from .ashby import AshbyScraper
from .base import Scraper
from .greenhouse import GreenhouseScraper
from .lever import LeverScraper
from .recruitee import RecruiteeScraper
from .smartrecruiters import SmartRecruitersScraper
from .workable import WorkableScraper

_SCRAPERS: dict[str, Scraper] = {
    s.name: s for s in [
        GreenhouseScraper(),
        LeverScraper(),
        AshbyScraper(),
        RecruiteeScraper(),
        WorkableScraper(),
        SmartRecruitersScraper(),
    ]
}

# Providers detect_ats will probe, in order of preference.
DETECTABLE = ["greenhouse", "lever", "ashby", "recruitee", "smartrecruiters", "workable"]


def get_scraper(ats: str) -> Scraper | None:
    return _SCRAPERS.get(ats)


def supported() -> list[str]:
    return list(_SCRAPERS.keys())
