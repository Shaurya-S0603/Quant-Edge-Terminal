"""Long-only trend and volatility overlay for an approved comparison basket."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from math import isfinite, log, sqrt
from pathlib import Path
from statistics import stdev

from .comparison import Costs, Session
from .split import Split


@dataclass(frozen=True, order=True)
class TrendRule:
    momentum_sessions: int
    volatility_sessions: int
    volatility_ceiling: float

    def __post_init__(self) -> None:
        if type(self.momentum_sessions) is not int or not 2 <= self.momentum_sessions <= 500:
            raise ValueError("Momentum lookback must be 2–500 sessions.")
        if type(self.volatility_sessions) is not int or not 2 <= self.volatility_sessions <= 500:
            raise ValueError("Volatility lookback must be 2–500 sessions.")
        if not isfinite(self.volatility_ceiling) or not 0 < self.volatility_ceiling <= 1:
            raise ValueError("Annualized volatility ceiling must be between zero and one.")


def targets_at_close(
    history: Sequence[Session], anchor: Mapping[str, float], rule: TrendRule,
) -> dict[str, float]:
    """Leave unallocated weight in cash. No name can exceed its anchor target."""
    required = max(rule.momentum_sessions, rule.volatility_sessions) + 1
    if len(history) < required:
        return dict.fromkeys(anchor, 0.0)
    trailing = history[-(rule.volatility_sessions + 1):]
    current, past = history[-1], history[-(rule.momentum_sessions + 1)]
    targets: dict[str, float] = {}
    for ticker, weight in anchor.items():
        if current.prices[ticker].feature_close <= past.prices[ticker].feature_close:
            targets[ticker] = 0.0
            continue
        daily = [log(bar.prices[ticker].feature_close) for bar in trailing]
        volatility = stdev(b - a for a, b in zip(daily, daily[1:])) * sqrt(252)
        targets[ticker] = weight * min(1.0, rule.volatility_ceiling / volatility) if volatility else weight
    return targets


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    baseline_id: str
    baseline_sha256: str
    split: Split
    default_rule: TrendRule
    grid: tuple[TrendRule, ...]
    costs: Costs
    digest: str


def load_strategy(path: Path) -> StrategySpec:
    payload = path.read_bytes()
    data = json.loads(payload)
    split = Split(
        date.fromisoformat(data["development_start"]),
        date.fromisoformat(data["development_end_exclusive"]),
        date.fromisoformat(data["holdout_end_exclusive"]),
    )
    grid = tuple(sorted(TrendRule(**row) for row in data["walk_forward_grid"]))
    default = TrendRule(**data["default_rule"])
    if len(grid) != len(set(grid)) or default not in grid:
        raise ValueError("Use a unique walk-forward grid containing the default rule.")
    return StrategySpec(
        data["id"], data["baseline_id"], data["baseline_sha256"], split, default, grid,
        Costs(data["fee_bps"], data["slippage_bps"]), sha256(payload).hexdigest(),
    )
