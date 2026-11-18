from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from quantedge_research.comparison import Prices, Session
from quantedge_research.synthetic_comparison import synthetic_sessions
from quantedge_research.synthetic_strategy import strategy_report
from quantedge_research.trend_strategy import TrendRule, load_strategy, targets_at_close
from quantedge_research.walk_forward import walk_forward

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "strategy-trend-volatility-v1.json"
PORTFOLIO = ROOT / "approved-portfolio-v1.json"


def bar(day, up, down, *, up_signal=None):
    return Session(day, datetime.combine(day, time(12), UTC), datetime.combine(day, time(19), UTC),
                   {"UP": Prices(up, up, up_signal), "DOWN": Prices(down, down)})


def test_trend_target_keeps_negative_signal_in_cash_preserves_caps_and_respects_adjusted_feature():
    start = date(2023, 1, 1)
    rule = TrendRule(2, 2, 0.20)
    history = [
        bar(start, 100, 100),
        bar(start + timedelta(days=1), 110, 95),
        bar(start + timedelta(days=2), 54, 90, up_signal=108),
    ]
    anchor = {"UP": 0.6, "DOWN": 0.4}
    assert targets_at_close(history[:2], anchor, rule) == {"UP": 0, "DOWN": 0}
    target = targets_at_close(history, anchor, rule)
    assert 0 < target["UP"] < 0.6
    assert target["DOWN"] == 0
    assert sum(target.values()) < 1


def test_full_strategy_smoke_and_fold_boundaries():
    result = strategy_report(SPEC, PORTFOLIO, 100_000)
    assert not result["holdout_evaluated"] and not result["has_real_market_prices"]
    for market, currency in (("US", "USD"), ("NSE", "INR")):
        sleeve = result["sleeves"][market]
        assert sleeve["currency"] == currency and len(sleeve["folds"]) == 6
        for fold in sleeve["folds"]:
            assert fold["train_last_session"] < fold["validation_start"]
            assert fold["validation_end_exclusive"] <= "2024-11-01"
            assert len(fold["training_trials"]) == 6


def test_validation_perturbation_does_not_change_first_training_choice():
    spec = load_strategy(SPEC)
    series = synthetic_sessions("US", {"UP", "REF"}, start=spec.split.start, end=spec.split.holdout_start)
    anchor = {"UP": 1.0}
    original = walk_forward(series, anchor, "REF", spec, 10_000)["folds"][0]
    altered = tuple(
        day if day.day < date(2018, 11, 1) else Session(
            day.day, day.market_open_at, day.close_available_at,
            {ticker: Prices(100, 100) for ticker in day.prices},
        )
        for day in series
    )
    new = walk_forward(altered, anchor, "REF", spec, 10_000)["folds"][0]
    assert new["selected_rule"] == original["selected_rule"]
    assert new["training_trials"] == original["training_trials"]
    assert new["fixed_rule"] != original["fixed_rule"]
    holdout = bar(spec.split.holdout_start, 100, 100)
    with pytest.raises(ValueError, match="development dates only"):
        walk_forward((*series, holdout), anchor, "REF", spec, 10_000)
