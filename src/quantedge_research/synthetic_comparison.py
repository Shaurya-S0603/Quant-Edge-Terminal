"""Reproducible, fabricated-market smoke run for the approved portfolio."""

import argparse
from datetime import date, timedelta
from hashlib import sha256
import json
from math import exp
from pathlib import Path
from random import Random

from .baseline import Baseline, load_baseline
from .comparison import Costs, Prices, Session, simulate
from .data import session_schedule

START = date(2023, 1, 1)
END = date(2024, 1, 1)
SEED = 4127


def synthetic_sessions(market: str, tickers: set[str]) -> tuple[Session, ...]:
    """Assign reproducible fabricated prices to local exchange sessions."""
    schedule = session_schedule(market, START, END)
    market_random = Random(int.from_bytes(sha256(f"{SEED}:{market}".encode()).digest()[:8]))
    asset_random = {
        ticker: Random(int.from_bytes(sha256(f"{SEED}:{market}:{ticker}".encode()).digest()[:8]))
        for ticker in sorted(tickers)
    }
    last_close = dict.fromkeys(sorted(tickers), 100.0)
    result: list[Session] = []
    for day, times in schedule.iterrows():
        overnight = market_random.gauss(0, 0.004)
        intraday = market_random.gauss(0.0001, 0.008)
        prices = {}
        for ticker, rng in asset_random.items():
            opening = last_close[ticker] * exp(overnight + rng.gauss(0, 0.003))
            closing = opening * exp(intraday + rng.gauss(0, 0.006))
            prices[ticker] = Prices(opening, closing)
            last_close[ticker] = closing
        result.append(Session(
            day.date(), times.market_open.to_pydatetime(),
            times.market_close.to_pydatetime() + timedelta(minutes=30), prices,
        ))
    return tuple(result)


def comparison_report(baseline: Baseline, costs: Costs, initial_cash: float) -> dict:
    sleeves = {}
    for benchmark in baseline.benchmarks:
        market = benchmark.market
        target = baseline.target_weights(market)
        sessions = synthetic_sessions(market, set(target) | {benchmark.ticker})
        gross = simulate(sessions, target, initial_cash=initial_cash, costs=Costs(0, 0))
        net = simulate(sessions, target, initial_cash=initial_cash, costs=costs)
        reference = simulate(
            sessions, {benchmark.ticker: 1.0}, initial_cash=initial_cash,
            costs=costs, rebalance_monthly=False,
        )
        sleeves[market] = {
            "currency": benchmark.currency, "reference_etf_label": benchmark.ticker,
            "targets": target, "sessions": len(sessions),
            "first_fill_session": net.fills[0].session.isoformat(),
            "gross": gross.metrics(), "net": net.metrics(), "net_etf": reference.metrics(),
        }
    return {
        "data": "synthetic_fixture", "has_real_market_prices": False,
        "baseline_id": baseline.baseline_id, "baseline_sha256": baseline.digest,
        "seed": SEED, "first_date": START.isoformat(), "end_exclusive": END.isoformat(),
        "initial_cash_per_sleeve": initial_cash, "fee_bps": costs.fee_bps,
        "slippage_bps": costs.slippage_bps, "sleeves": sleeves,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path("research/approved-portfolio-v1.json"))
    parser.add_argument("--cash", type=float, default=100_000)
    parser.add_argument("--fee-bps", type=float, default=5)
    parser.add_argument("--slippage-bps", type=float, default=10)
    args = parser.parse_args()
    result = comparison_report(load_baseline(args.baseline), Costs(args.fee_bps, args.slippage_bps), args.cash)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
