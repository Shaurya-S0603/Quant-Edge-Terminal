"""Versioned comparison portfolio shared by audits and the research engine."""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from .data import Instrument

PROFILES = {"high_volatility", "liquid_large_cap", "slow_moving", "dividend_stability"}


@dataclass(frozen=True)
class Holding:
    instrument: Instrument
    name: str
    sector: str
    industry: str
    profile: str
    target_weight_bps: int

    def __post_init__(self) -> None:
        if type(self.target_weight_bps) is not int or not 0 < self.target_weight_bps <= 10_000:
            raise ValueError("Target weights must be positive integer basis points.")
        if self.profile not in PROFILES:
            raise ValueError(f"Unknown portfolio profile: {self.profile}")


@dataclass(frozen=True)
class Baseline:
    baseline_id: str
    approved_on: date
    screening_start: date
    screening_end_exclusive: date
    digest: str
    holdings: tuple[Holding, ...]
    benchmarks: tuple[Instrument, ...]

    @property
    def instruments(self) -> tuple[Instrument, ...]:
        return tuple(holding.instrument for holding in self.holdings) + self.benchmarks

    def target_weights(self, market: str) -> dict[str, float]:
        """Within-market targets for portfolios denominated in local currency."""
        targets = {
            holding.instrument.ticker: holding.target_weight_bps
            for holding in self.holdings
            if holding.instrument.market == market
        }
        if not targets:
            raise ValueError(f"No holdings for market {market!r}.")
        total = sum(targets.values())
        return {ticker: weight / total for ticker, weight in targets.items()}


def load_baseline(path: Path) -> Baseline:
    payload = path.read_bytes()
    data = json.loads(payload)
    if data["version"] != 1:
        raise ValueError("Unsupported comparison portfolio schema.")
    holdings = tuple(
        Holding(Instrument(row["instrument_id"], row["ticker"], row["market"], row["currency"]),
                row["name"], row["sector"], row["industry"], row["profile"], row["target_weight_bps"])
        for row in data["holdings"]
    )
    benchmarks = tuple(Instrument(**row, role="benchmark") for row in data["market_benchmarks"])
    dates = data["screening_returns"]
    baseline = Baseline(
        data["baseline_id"], date.fromisoformat(data["approved_on"]),
        date.fromisoformat(dates["start"]), date.fromisoformat(dates["end_exclusive"]),
        sha256(payload).hexdigest(), holdings, benchmarks,
    )
    if not baseline.screening_start < baseline.screening_end_exclusive <= baseline.approved_on:
        raise ValueError("Baseline screening dates must precede approval.")
    if sum(holding.target_weight_bps for holding in holdings) != 10_000:
        raise ValueError("Portfolio weights must sum to 10,000 basis points.")
    markets = {holding.instrument.market for holding in holdings}
    if markets != {benchmark.market for benchmark in benchmarks} or len(benchmarks) != len(markets):
        raise ValueError("Each market must have exactly one comparison benchmark.")
    instruments = baseline.instruments
    if len({i.instrument_id for i in instruments}) != len(instruments):
        raise ValueError("Baseline instrument IDs must be unique.")
    if len({(i.market, i.ticker) for i in instruments}) != len(instruments):
        raise ValueError("Baseline market and ticker pairs must be unique.")
    return baseline
