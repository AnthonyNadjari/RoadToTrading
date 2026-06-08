"""Maps an ATS name -> scraper instance, and lists detectable providers."""
from __future__ import annotations

from .ashby import AshbyScraper
from .base import Scraper, QueryScraper
from .efinancialcareers import EfcScraper
from .greenhouse import GreenhouseScraper
from .lever import LeverScraper
from .linkedin import LinkedInScraper
from .recruitee import RecruiteeScraper
from .smartrecruiters import SmartRecruitersScraper
from .workable import WorkableScraper
from .workday import WorkdayScraper

_SCRAPERS: dict[str, Scraper] = {
    s.name: s for s in [
        GreenhouseScraper(),
        LeverScraper(),
        AshbyScraper(),
        RecruiteeScraper(),
        WorkableScraper(),
        SmartRecruitersScraper(),
        WorkdayScraper(),
    ]
}

_QUERY_SCRAPERS: dict[str, QueryScraper] = {
    s.name: s for s in [LinkedInScraper(), EfcScraper()]
}

# Providers detect_ats will probe, in order of preference.
DETECTABLE = ["greenhouse", "lever", "ashby", "recruitee", "smartrecruiters", "workable"]
# Sources that discover the market but must not drive CLOSED inference.
QUERY_SOURCE_NAMES = set(_QUERY_SCRAPERS)


def get_scraper(ats: str) -> Scraper | None:
    return _SCRAPERS.get(ats)


def get_query_scraper(name: str) -> QueryScraper | None:
    return _QUERY_SCRAPERS.get(name)


def supported() -> list[str]:
    return list(_SCRAPERS.keys())
