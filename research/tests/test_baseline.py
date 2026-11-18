from argparse import Namespace
from collections import Counter
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest

from quantedge_research.__main__ import coverage_report
from quantedge_research.baseline import load_baseline
from quantedge_research.data import REQUIRED_COLUMNS

CONFIG = Path(__file__).resolve().parents[1] / "approved-portfolio-v1.json"


def test_approved_baseline_keeps_exact_weights_and_benchmarks():
    baseline = load_baseline(CONFIG)
    expected = {
        "NVDA": 300, "TSLA": 300, "ADANIPORTS.NS": 300, "HINDALCO.NS": 300,
        "MSFT": 900, "AMZN": 900, "RELIANCE.NS": 900, "HDFCBANK.NS": 900,
        "WM": 600, "JNJ": 600, "HINDUNILVR.NS": 600, "SUNPHARMA.NS": 600,
        "KO": 700, "DUK": 700, "POWERGRID.NS": 700, "ITC.NS": 700,
    }
    assert {h.instrument.ticker: h.target_weight_bps for h in baseline.holdings} == expected
    totals = Counter()
    for holding in baseline.holdings:
        totals[holding.instrument.market] += holding.target_weight_bps
    assert totals == {"US": 5_000, "NSE": 5_000}
    assert baseline.target_weights("US")["MSFT"] == 0.18
    assert baseline.target_weights("NSE")["ITC.NS"] == 0.14
    assert {item.ticker for item in baseline.benchmarks} == {"SPY", "NIFTYBEES.NS"}


def test_baseline_rejects_weight_drift(tmp_path):
    config = tmp_path / "drift.json"
    values = json.loads(CONFIG.read_bytes())
    values["holdings"][0]["target_weight_bps"] += 100
    config.write_text(json.dumps(values))
    with pytest.raises(ValueError, match="10,000"):
        load_baseline(config)


def test_coverage_uses_config_identity_and_refuses_screening_overlap(monkeypatch, tmp_path):
    from quantedge_research import __main__ as cli

    monkeypatch.setattr(cli, "read_csv", lambda _: pd.DataFrame(columns=REQUIRED_COLUMNS))
    args = Namespace(
        baseline=CONFIG, universe=None, prices_dir=tmp_path, price_basis="raw",
        source_name="fixture", end_exclusive=date(2026, 11, 1),
    )
    report = coverage_report(args)
    assert report["requested"] == len(report["audits"]) == 18
    assert not report["failures"]
    assert report["baseline"]["sha256"] == sha256(CONFIG.read_bytes()).hexdigest()
    assert report["eligible_for_final_holdout"] is False
    args.end_exclusive = date(2026, 10, 1)
    with pytest.raises(ValueError, match="overlaps"):
        coverage_report(args)
