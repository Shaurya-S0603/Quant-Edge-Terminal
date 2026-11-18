from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from quantedge_research.baseline import load_baseline
from quantedge_research.comparison import Costs, Prices, Session, simulate
from quantedge_research.synthetic_comparison import comparison_report


def session(iso, *, a=(100, 100), b=(100, 100), close_hour=20):
    day = date.fromisoformat(iso)
    return Session(
        day, datetime.combine(day, time(13), UTC), datetime.combine(day, time(close_hour), UTC),
        {"A": Prices(*a), "B": Prices(*b)},
    )


def test_orders_use_prior_close_quantities_and_cash_scales_open_fills():
    sessions = [session("2023-01-03"), session("2023-01-04", a=(120, 120))]
    result = simulate(sessions, {"A": 0.5, "B": 0.5}, initial_cash=1_000, costs=Costs(50, 100))
    assert not result.points[0].positions["A"]
    scale = 1_000 / (1_100 * 1.015)
    for fill in result.fills:
        assert fill.decision_at == sessions[0].close_available_at
        assert fill.filled_at == sessions[1].market_open_at
        assert fill.requested_quantity == 5
        assert fill.quantity == pytest.approx(5 * scale)
    metrics = result.metrics()
    assert result.points[-1].cash == pytest.approx(0)
    assert metrics["ending_equity"] + metrics["fees"] + metrics["slippage"] == pytest.approx(1_000)


def test_monthly_rebalance_does_not_change_earlier_fills_and_executes_sells_first():
    sessions = [
        session("2023-01-03"), session("2023-01-04"),
        session("2023-02-01", a=(100, 200)),
        session("2023-02-02", a=(200, 80)),
    ]
    kwargs = dict(initial_cash=1_000, costs=Costs(0, 0))
    weights = {"A": 0.5, "B": 0.5}
    prefix = simulate(sessions[:-1], weights, **kwargs)
    full = simulate(sessions, weights, **kwargs)
    assert prefix.points == full.points[:-1]
    assert prefix.fills == full.fills[:len(prefix.fills)]
    sell, buy = full.fills[-2:]
    assert (sell.ticker, sell.quantity) == ("A", -1.25)
    assert (buy.ticker, buy.quantity) == ("B", 2.5)
    assert sell.decision_at == sessions[2].close_available_at
    assert full.metrics()["max_drawdown"] == pytest.approx(0.3)


def test_benchmark_holds_after_initial_order_and_late_inputs_fail_closed():
    sessions = [session(day) for day in ("2023-01-03", "2023-01-04", "2023-02-01", "2023-02-02")]
    kwargs = dict(initial_cash=100, costs=Costs(0, 0))
    assert len(simulate(sessions, {"A": 1.0}, rebalance_monthly=False, **kwargs).fills) == 1
    decision = Session(sessions[0].day, sessions[0].market_open_at,
                       sessions[1].market_open_at, sessions[0].prices)
    with pytest.raises(ValueError, match="before the next session"):
        simulate([decision, *sessions[1:]], {"A": 1.0}, **kwargs)


def test_approved_baseline_smoke_run_is_deterministic_and_local_currency_only():
    config = Path(__file__).resolve().parents[1] / "approved-portfolio-v1.json"
    baseline = load_baseline(config)
    args = baseline, Costs(5, 10), 100_000
    result = comparison_report(*args)
    assert result == comparison_report(*args)
    assert result["data"] == "synthetic_fixture" and not result["has_real_market_prices"]
    assert "combined" not in result
    for market, currency in (("US", "USD"), ("NSE", "INR")):
        sleeve = result["sleeves"][market]
        assert sleeve["currency"] == currency
        assert sleeve["targets"] == baseline.target_weights(market)
        assert sleeve["gross"]["fees"] == 0 and sleeve["net"]["fees"] > 0
        assert sleeve["net_etf"]["fill_count"] == 1
