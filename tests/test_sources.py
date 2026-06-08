"""Tests for the company resolver, Workday id extraction, and eFC parser."""
from __future__ import annotations

from jobintel.employers_index import resolve, normalize_name
from jobintel.scrapers.workday import _REQ
from jobintel.scrapers.efinancialcareers import _extract_objects


def test_resolve_watchlist_exact():
    eid, name, etype = resolve("Jane Street")
    assert eid == "janestreet" and etype == "PROP"


def test_resolve_alias():
    assert resolve("Susquehanna")[0] == "sig"
    assert resolve("Hudson River Trading")[0] == "hrt"


def test_resolve_unknown_is_external():
    eid, name, etype = resolve("Fasanara Capital")
    assert eid.startswith("ext-") and etype == "OTHER" and name == "Fasanara Capital"


def test_normalize_drops_legal_suffix():
    assert normalize_name("Two Sigma Investments, LLC") == "two sigma investments"


def test_workday_reqid():
    assert _REQ.search("/job/Canary-Wharf/Trader_JR-0000109479").group(1) == "JR-0000109479"


def test_efc_brace_extractor():
    blob = ('garbage {"id":"x1","title":"Trader","companyName":"Point72",'
            '"location":{"city":"London"}} more {"id":"x2","title":"Strat",'
            '"companyName":"Citadel"} tail')
    objs = _extract_objects(blob)
    assert len(objs) == 2
    assert objs[0]["companyName"] == "Point72" and objs[0]["location"]["city"] == "London"
    assert objs[1]["title"] == "Strat"


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
