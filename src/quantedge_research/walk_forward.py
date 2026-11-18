"""Expanding-window rule comparison on development sessions only."""

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from math import prod, sqrt
from statistics import mean, stdev

from .comparison import Costs, Session, Simulation, simulate
from .trend_strategy import StrategySpec, TrendRule, targets_at_close


def _net_sharpe(run: Simulation) -> float | None:
    levels = [run.initial_cash, *(point.equity for point in run.points)]
    returns = [after / before - 1 for before, after in zip(levels, levels[1:])]
    volatility = stdev(returns)
    if volatility <= 1e-12:
        return None
    return mean(returns) / volatility * sqrt(252)


def _simulate_rule(
    sessions: Sequence[Session], anchor: Mapping[str, float], rule: TrendRule,
    initial_cash: float, costs: Costs, *, warmup: Sequence[Session] = (),
) -> Simulation:
    return simulate(
        sessions, anchor, initial_cash=initial_cash, costs=costs,
        policy=lambda history: targets_at_close(history, anchor, rule), warmup=warmup,
    )


def _metrics(run: Simulation) -> dict:
    return run.metrics() | {"net_sharpe": _net_sharpe(run)}


def _training_trials(
    training: Sequence[Session], warmup: Sequence[Session], anchor: Mapping[str, float],
    spec: StrategySpec, initial_cash: float,
) -> tuple[TrendRule, list[dict]]:
    best = spec.default_rule
    best_sharpe = float("-inf")
    trials = []
    for rule in spec.grid:
        run = _simulate_rule(training, anchor, rule, initial_cash, spec.costs, warmup=warmup)
        score = _net_sharpe(run)
        trials.append({"rule": asdict(rule), "net_sharpe": score, "return": run.metrics()["return"]})
        if score is not None and score > best_sharpe:
            best, best_sharpe = rule, score
    return best, trials


def walk_forward(
    sessions: Sequence[Session], anchor: Mapping[str, float], benchmark: str,
    spec: StrategySpec, initial_cash: float,
) -> dict:
    """Fit on strictly earlier dates. Compare on annually restarted ledgers.

    No forward-return labels are constructed; each trial scores a simulation
    confined to its train slice. The validation signal can warm up on train
    closes, but all three comparison ledgers begin each fold in cash.
    """
    start = spec.split.start
    boundary = spec.split.holdout_start
    dates = [session.day for session in sessions]
    if not dates or any(not start <= day < boundary for day in dates):
        raise ValueError("Walk-forward input must contain development dates only.")
    if any(first >= second for first, second in zip(dates, dates[1:])):
        raise ValueError("Development dates must be unique and increasing.")
    validation_start = start.replace(year=start.year + 2)
    folds = []
    warmup_size = max(max(rule.momentum_sessions, rule.volatility_sessions) + 1 for rule in spec.grid)
    while validation_start < boundary:
        end = min(validation_start.replace(year=validation_start.year + 1), boundary)
        training = tuple(session for session in sessions if session.day < validation_start)
        validation = tuple(session for session in sessions if validation_start <= session.day < end)
        if len(training) < warmup_size + 2 or len(validation) < 2:
            raise ValueError(f"Insufficient development coverage for fold starting {validation_start}.")
        selected, trials = _training_trials(
            training[warmup_size:], training[:warmup_size], anchor, spec, initial_cash,
        )
        warmup = training[-warmup_size:]
        test = _simulate_rule(validation, anchor, selected, initial_cash, spec.costs, warmup=warmup)
        default = _simulate_rule(validation, anchor, spec.default_rule, initial_cash, spec.costs, warmup=warmup)
        fixed = simulate(validation, anchor, initial_cash=initial_cash, costs=spec.costs)
        reference = simulate(
            validation, {benchmark: 1.0}, initial_cash=initial_cash,
            costs=spec.costs, rebalance_monthly=False,
        )
        folds.append({
            "train_first_session": training[0].day.isoformat(),
            "train_last_session": training[-1].day.isoformat(),
            "train_scoring_first_session": training[warmup_size].day.isoformat(),
            "validation_start": validation_start.isoformat(),
            "validation_end_exclusive": end.isoformat(),
            "validation_sessions": len(validation),
            "selected_rule": asdict(selected),
            "training_trials": trials,
            "walk_forward": _metrics(test),
            "fixed_rule": _metrics(default),
            "fixed_weights": _metrics(fixed),
            "reference": _metrics(reference),
        })
        validation_start = end
    summary = {
        key: prod(1 + fold[key]["return"] for fold in folds) - 1
        for key in ("walk_forward", "fixed_rule", "fixed_weights", "reference")
    }
    return {"folds": folds, "linked_validation_returns": summary}
