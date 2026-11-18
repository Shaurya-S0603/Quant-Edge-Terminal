"""Run the deliverable strategy and its development-only synthetic dry run."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .baseline import load_baseline
from .synthetic_comparison import SEED, synthetic_sessions
from .trend_strategy import load_strategy
from .walk_forward import walk_forward


def strategy_report(strategy_path: Path, portfolio_path: Path, initial_cash: float) -> dict:
    spec = load_strategy(strategy_path)
    baseline = load_baseline(portfolio_path)
    if baseline.baseline_id != spec.baseline_id or baseline.digest != spec.baseline_sha256:
        raise ValueError("The strategy expects a different approved comparison basket.")
    if not spec.split.start <= baseline.screening_start < baseline.screening_end_exclusive <= spec.split.holdout_start:
        raise ValueError("The approved basket screening dates must fall inside development.")
    sleeves = {}
    for benchmark in baseline.benchmarks:
        market = benchmark.market
        anchor = baseline.target_weights(market)
        sessions = synthetic_sessions(
            market, set(anchor) | {benchmark.ticker},
            start=spec.split.start, end=spec.split.holdout_start,
        )
        sleeves[market] = {
            "currency": benchmark.currency, "reference_ticker_label": benchmark.ticker,
            "anchor_weights": anchor,
            **walk_forward(sessions, anchor, benchmark.ticker, spec, initial_cash),
        }
    return {
        "data": "synthetic_fixture", "has_real_market_prices": False,
        "strategy_id": spec.strategy_id, "strategy_sha256": spec.digest,
        "baseline_sha256": baseline.digest, "seed": SEED, "split_dates": spec.split.dates(),
        "holdout_evaluated": False, "default_rule": asdict(spec.default_rule),
        "costs": asdict(spec.costs), "initial_cash_per_fold": initial_cash, "sleeves": sleeves,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", type=Path, default=Path("research/strategy-trend-volatility-v1.json"))
    parser.add_argument("--baseline", type=Path, default=Path("research/approved-portfolio-v1.json"))
    parser.add_argument("--cash", type=float, default=100_000)
    args = parser.parse_args()
    print(json.dumps(strategy_report(args.strategy, args.baseline, args.cash), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
