"""Exploratory Yahoo Finance development replay. Does not access the holdout."""

from argparse import ArgumentParser
from collections.abc import Mapping
from dataclasses import asdict
from datetime import date, timedelta
from hashlib import sha256
import json
from math import isclose, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from .baseline import Baseline, load_baseline
from .comparison import Costs, Prices, Session, Simulation, simulate
from .data import session_schedule
from .trend_strategy import StrategySpec, load_strategy, targets_at_close
from .walk_forward import walk_forward
from .yahoo import fetch_provider_history

PRICE_FIELDS = ("Open", "High", "Low", "Close", "Adj Close")
KNOWN_GAPS = {"US": (), "NSE": ("2019-02-13", "2019-03-29")}
INITIAL_CASH = 100_000.0
# Official NSE EQ bhavcopy on the new unit scale. See the replay research notes.
NIFTYBEES_UNIT_CHECKS = {
    date(2019, 12, 19): (129.20, 130.33, 129.05, 130.20),
    date(2019, 12, 20): (134.95, 134.95, 129.78, 130.34),
}


def adjusted_prices(
    source: pd.DataFrame, start: date, end: date, *, ticker: str,
) -> tuple[dict[date, Prices], list[str]]:
    """Check the delivered OHLCV and construct a total-return execution proxy."""
    fields = ["session", *PRICE_FIELDS, "Volume"]
    if not source.columns.is_unique or not set(fields) <= set(source):
        raise ValueError("Yahoo history is missing expected OHLCV or adjusted close columns.")
    sessions = [date.fromisoformat(str(label)) for label in source["session"]]
    if not sessions or len(set(sessions)) != len(sessions) or sessions != sorted(sessions):
        raise ValueError("Expected nonempty, unique and ordered Yahoo sessions.")
    if any(not start <= day < end for day in sessions):
        raise ValueError("Yahoo snapshot must contain only development dates.")
    bars = source.loc[:, fields[1:]].astype(float).reset_index(drop=True)
    if (not np.isfinite(bars.to_numpy()).all()
            or (bars[list(PRICE_FIELDS)] <= 0).any().any()
            or (bars["Volume"] < 0).any()
            or (bars["High"] < bars[["Open", "Close", "Low"]].max(axis=1)).any()
            or (bars["Low"] > bars[["Open", "Close"]].min(axis=1)).any()):
        raise ValueError("Yahoo bars contain an invalid price, range, or volume.")
    normalized = []
    if ticker == "NIFTYBEES.NS":
        for day, expected in NIFTYBEES_UNIT_CHECKS.items():
            row = sessions.index(day)
            observed = bars.loc[row, list(PRICE_FIELDS[:4])].to_numpy()
            if np.allclose(observed, expected, rtol=0, atol=0.001):
                continue
            if not np.allclose(observed * 10, expected, rtol=0, atol=0.001):
                raise ValueError(f"Unexpected NIFTYBEES.NS split basis on {day}.")
            bars.loc[row, list(PRICE_FIELDS)] *= 10
            normalized.append(day.isoformat())
    suspicious = bars["Adj Close"].pct_change().abs().gt(0.40)
    if suspicious.any():
        raise ValueError(f"Unreviewed daily return above 40% for {ticker} on {sessions[suspicious.idxmax()]}.")
    opened = bars["Open"] * (bars["Adj Close"] / bars["Close"])
    return ({
        day: Prices(float(open_price), float(close_price))
        for day, open_price, close_price in zip(sessions, opened, bars["Adj Close"], strict=True)
    }, normalized)


def aligned_sessions(
    market: str, histories: Mapping[str, dict[date, Prices]], spec: StrategySpec,
) -> tuple[tuple[Session, ...], dict]:
    schedule = session_schedule(market, spec.split.start, spec.split.holdout_start)
    calendar = {label.date() for label in schedule.index}
    common = set.intersection(*(set(history) for history in histories.values()))
    missing = sorted(calendar - common)
    if tuple(day.isoformat() for day in missing) != KNOWN_GAPS[market]:
        raise ValueError(f"{market} aligned dates differ from the documented exclusions: {missing}")
    off_calendar = sorted(set.union(*(set(history) for history in histories.values())) - calendar)
    if off_calendar:
        raise ValueError(f"{market} has unexpected off-calendar bars: {off_calendar}")
    rows = tuple(
        Session(
            label.date(), row.market_open.to_pydatetime(),
            row.market_close.to_pydatetime() + timedelta(minutes=30),
            {ticker: history[label.date()] for ticker, history in histories.items()},
        )
        for label, row in schedule.iterrows() if label.date() in common
    )
    return rows, {
        "sessions_expected": len(calendar),
        "sessions_used": len(rows),
        "missing_sessions": [day.isoformat() for day in missing],
        "first_session": rows[0].day.isoformat(),
        "last_session": rows[-1].day.isoformat(),
    }


def daily_returns(run: Simulation) -> np.ndarray:
    levels = np.array([run.initial_cash, *(point.equity for point in run.points)])
    return levels[1:] / levels[:-1] - 1.0


def summarize(run: Simulation, start: date, end: date) -> dict:
    returns = daily_returns(run)
    volatility = returns.std(ddof=1) * sqrt(252)
    years = (end - start).days / 365.2425
    summary = run.metrics()
    return summary | {
        "cagr": (1.0 + summary["return"]) ** (1.0 / years) - 1.0,
        "volatility": float(volatility),
        "sharpe": float(returns.mean() * 252 / volatility) if volatility else None,
        "mean_cash_weight": float(np.mean([point.cash / point.equity for point in run.points])),
    }


def bootstrap(
    strategy: np.ndarray, fixed: np.ndarray, *, block: int, paths: int = 2000,
    steps: int = 252, seed: int = 41321,
) -> dict:
    """Compound synchronized moving blocks of realized portfolio returns."""
    if (strategy.ndim != 1 or strategy.shape != fixed.shape or not 1 <= block <= len(strategy)
            or paths < 1 or steps < 1 or not np.isfinite(strategy).all()
            or not np.isfinite(fixed).all() or (strategy <= -1).any() or (fixed <= -1).any()):
        raise ValueError("Paired finite return histories and a valid resampling shape are required.")
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(strategy) - block + 1, size=(paths, (steps + block - 1) // block))
    indices = (starts[:, :, None] + np.arange(block)).reshape(paths, -1)[:, :steps]

    def wealth(returns: np.ndarray) -> np.ndarray:
        levels = np.cumprod(1 + returns[indices], axis=1) * 100
        return np.column_stack((np.full(paths, 100.0), levels))

    overlay, baseline = wealth(strategy), wealth(fixed)
    quantiles = np.quantile(overlay, [.05, .25, .50, .75, .95], axis=0)
    return {
        "block": block, "paths": paths, "steps": steps, "seed": seed,
        "bands": {
            key: series.round(4).tolist()
            for key, series in zip(("p05", "p25", "p50", "p75", "p95"), quantiles, strict=True)
        },
        "fixed_median": np.quantile(baseline, .50, axis=0).round(4).tolist(),
        "fraction_below_start": float(np.mean(overlay[:, -1] < 100)),
        "fraction_beating_fixed": float(np.mean(overlay[:, -1] > baseline[:, -1])),
    }


def replay_market(
    baseline: Baseline, spec: StrategySpec, market: str, histories: Mapping[str, dict[date, Prices]],
) -> dict:
    sessions, coverage = aligned_sessions(market, histories, spec)
    anchor = baseline.target_weights(market)
    benchmark = next(item for item in baseline.benchmarks if item.market == market)
    rule = spec.default_rule
    # Start all four continuous ledgers after identical feature warmup.
    warmup_size = max(rule.momentum_sessions, rule.volatility_sessions) + 1
    warmup, scoring = sessions[:warmup_size], sessions[warmup_size:]

    def overlay(costs: Costs) -> Simulation:
        return simulate(
            scoring, anchor, initial_cash=INITIAL_CASH, costs=costs, warmup=warmup,
            policy=lambda history: targets_at_close(history, anchor, rule),
        )

    runs = {
        "net": overlay(spec.costs),
        "gross": overlay(Costs(0, 0)),
        "fixed": simulate(scoring, anchor, initial_cash=INITIAL_CASH, costs=spec.costs),
        "benchmark": simulate(
            scoring, {benchmark.ticker: 1.0}, initial_cash=INITIAL_CASH,
            costs=spec.costs, rebalance_monthly=False,
        ),
    }
    return {
        "currency": benchmark.currency, "benchmark": benchmark.ticker, "coverage": coverage,
        "scoring_start": scoring[0].day.isoformat(),
        "warmup_sessions": warmup_size,
        "holdings": [
            {"symbol": item.instrument.ticker, "name": item.name, "profile": item.profile,
             "weight": anchor[item.instrument.ticker]}
            for item in baseline.holdings if item.instrument.market == market
        ],
        "metrics": {
            key: summarize(run, scoring[0].day, spec.split.holdout_start) for key, run in runs.items()
        },
        "equity": {
            "dates": [session.day.isoformat() for session in scoring],
            **{
                key: [round(100 * point.equity / run.initial_cash, 4) for point in run.points]
                for key, run in runs.items()
            },
        },
        "bootstrap": {
            str(block): bootstrap(daily_returns(runs["net"]), daily_returns(runs["fixed"]), block=block)
            for block in (10, 20, 60)
        },
        "walk_forward": walk_forward(sessions, anchor, benchmark.ticker, spec, INITIAL_CASH),
    }


def build_report(baseline: Baseline, spec: StrategySpec, snapshot: Path, *, fetch: bool) -> dict:
    if (baseline.baseline_id, baseline.digest) != (spec.baseline_id, spec.baseline_sha256):
        raise ValueError("Strategy configuration must match the approved portfolio digest.")
    if fetch:
        snapshot.mkdir(parents=True, exist_ok=True)
    hashes, histories, corrections = {}, {}, {}
    for instrument in baseline.instruments:
        path = snapshot / f"{instrument.ticker}.csv"
        if fetch and not path.exists():
            frame = fetch_provider_history(instrument, spec.split.start, spec.split.holdout_start, snapshot / "cache")
            adjusted_prices(frame, spec.split.start, spec.split.holdout_start, ticker=instrument.ticker)
            pending = path.with_suffix(".tmp")
            frame.to_csv(pending, index=False)
            pending.replace(path)
        frame = pd.read_csv(path, float_precision="round_trip")
        prices, normalized = adjusted_prices(
            frame, spec.split.start, spec.split.holdout_start, ticker=instrument.ticker,
        )
        histories.setdefault(instrument.market, {})[instrument.ticker] = prices
        if normalized:
            corrections[instrument.ticker] = normalized
        hashes[instrument.ticker] = sha256(path.read_bytes()).hexdigest()
    return {
        "strategy_id": spec.strategy_id,
        "strategy_sha256": spec.digest,
        "baseline_sha256": baseline.digest,
        "development_start": spec.split.start.isoformat(),
        "development_end_exclusive": spec.split.holdout_start.isoformat(),
        "holdout_end_exclusive": spec.split.end_exclusive.isoformat(),
        "source": "Yahoo Finance",
        "provider_csv_sha256": hashes,
        "split_basis_corrections": corrections,
        "rule": asdict(spec.default_rule),
        "costs": asdict(spec.costs),
        "markets": {
            market: replay_market(baseline, spec, market, histories[market])
            for market in sorted(histories)
        },
    }


def site_payload(report: dict) -> dict:
    """Publish strategy aggregates and paths without shipping provider quotes."""
    markets = {}
    for market, results in report["markets"].items():
        visible = {key: results[key] for key in ("currency", "benchmark", "coverage", "metrics", "equity", "bootstrap")}
        visible["instrument_count"] = len(results["holdings"])
        visible["folds"] = [
            {"start": fold["validation_start"], **{
                key: fold[key]["return"] for key in ("fixed_rule", "walk_forward", "fixed_weights")
            }}
            for fold in results["walk_forward"]["folds"]
        ]
        visible["split_basis_corrections"] = report["split_basis_corrections"].get(results["benchmark"], [])
        markets[market] = visible
    return {"markets": markets}


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True, help="Private Yahoo CSV directory")
    parser.add_argument("--output", type=Path, required=True, help="Derived JSON report")
    parser.add_argument("--site-output", type=Path, help="Portfolio-only JSON for the static website")
    parser.add_argument("--baseline", type=Path, default=Path("research/approved-portfolio-v1.json"))
    parser.add_argument("--strategy", type=Path, default=Path("research/strategy-trend-volatility-v1.json"))
    parser.add_argument("--fetch", action="store_true", help="Fetch missing development CSVs only")
    args = parser.parse_args()
    report = build_report(load_baseline(args.baseline), load_strategy(args.strategy), args.snapshot, fetch=args.fetch)
    write_report(args.output, report)
    if args.site_output is not None:
        write_report(args.site_output, site_payload(report))


if __name__ == "__main__":
    main()
