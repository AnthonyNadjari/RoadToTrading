"""Regression tests for the deterministic classifier + normalizer.

Runs with pytest, or standalone:  python -m tests.test_classify
"""
from __future__ import annotations

from jobintel.normalize import normalize_title
from jobintel.classify import classify, is_target_geo


def _fam(title: str, dept=None, etype="MM") -> str:
    return classify(normalize_title(title), dept, etype).role_family


# --- role routing ---------------------------------------------------------- #
def test_specificity_beats_generic():
    # "Quantitative Trader" must not be absorbed by generic TRADING
    assert _fam("Quantitative Trader") == "QUANT_TRADING"
    assert _fam("Quant Trader - Equities") == "QUANT_TRADING"


def test_plain_trader_is_trading():
    assert _fam("Equity Options Trader") == "TRADING"
    assert _fam("Graduate Trader") == "TRADING"


def test_research_and_strats():
    assert _fam("Quantitative Researcher") == "QUANT_RESEARCH"
    assert _fam("Quantitative Strategist") == "STRATS"


def test_structuring():
    assert _fam("Equity Derivatives Structurer", etype="BANK") == "STRUCTURING"


def test_engineering_routed_to_quant_dev_not_trading():
    # the priority TRADING view must stay free of software/infra titles
    assert _fam("Software Engineer | Trading Team") in ("QUANT_DEV", "UNCLASSIFIED")
    assert _fam("Software Engineer | Trading Team") != "TRADING"
    assert _fam("Quantitative Developer") == "QUANT_DEV"


# --- scope / exclusions ---------------------------------------------------- #
def test_exclusions():
    for t in ["Risk Manager", "Compliance Officer", "Sales Trader",
              "Trading Operations Analyst", "M&A Analyst", "Fund Accountant"]:
        assert classify(normalize_title(t), None, "BANK").in_scope is False, t


def test_quant_dev_at_bank_requires_context():
    # generic bank dev without quant/trading context -> out
    c = classify(normalize_title("Core Developer"), None, "BANK")
    assert c.in_scope is False


# --- enrichment ------------------------------------------------------------ #
def test_seniority_and_assets():
    c = classify(normalize_title("Senior Quantitative Researcher - FX Options"),
                 None, "HF")
    assert c.seniority == "SENIOR"
    assert "FX" in c.asset_classes and "VOL_EXOTICS" in c.asset_classes


def test_target_geo():
    assert is_target_geo(["London, UK"]) is True
    assert is_target_geo(["Paris"]) is True
    assert is_target_geo(["New York"]) is False


# --- normalization --------------------------------------------------------- #
def test_normalize_strips_noise():
    assert normalize_title("Quantitative Trader (m/f/d)") == "quantitative trader"
    assert "req" not in normalize_title("Trader REQ-12345")


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
