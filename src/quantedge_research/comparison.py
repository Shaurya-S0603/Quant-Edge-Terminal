"""Daily fixed-weight comparison simulation with explicit execution timing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import fsum, isclose, isfinite


@dataclass(frozen=True)
class Prices:
    open: float
    close: float


@dataclass(frozen=True)
class Session:
    day: date
    market_open_at: datetime
    close_available_at: datetime
    prices: Mapping[str, Prices]


@dataclass(frozen=True)
class Costs:
    fee_bps: float
    slippage_bps: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) and v >= 0 for v in (self.fee_bps, self.slippage_bps)):
            raise ValueError("Trading costs must be finite and nonnegative.")
        if self.fee_bps + self.slippage_bps >= 10_000:
            raise ValueError("Combined trading costs must be less than the trade value.")


@dataclass(frozen=True)
class Fill:
    session: date
    ticker: str
    decision_at: datetime
    filled_at: datetime
    requested_quantity: float
    quantity: float
    reference_open: float
    fee: float
    slippage: float

    @property
    def notional(self) -> float:
        return abs(self.quantity) * self.reference_open


@dataclass(frozen=True)
class PortfolioPoint:
    session: date
    equity: float
    cash: float
    positions: Mapping[str, float]


@dataclass(frozen=True)
class Simulation:
    initial_cash: float
    points: tuple[PortfolioPoint, ...]
    fills: tuple[Fill, ...]
    turnover: float

    def metrics(self) -> dict:
        peak = self.initial_cash
        drawdown = 0.0
        for point in self.points:
            peak = max(peak, point.equity)
            drawdown = max(drawdown, 1.0 - point.equity / peak)
        return {
            "ending_equity": self.points[-1].equity,
            "return": self.points[-1].equity / self.initial_cash - 1.0,
            "max_drawdown": drawdown,
            "turnover": self.turnover,
            "fees": fsum(fill.fee for fill in self.fills),
            "slippage": fsum(fill.slippage for fill in self.fills),
            "fill_count": len(self.fills),
        }


@dataclass(frozen=True)
class _OrderBatch:
    decided_at: datetime
    quantities: Mapping[str, float]


def _validate_inputs(sessions: Sequence[Session], weights: Mapping[str, float], initial_cash: float) -> None:
    if len(sessions) < 2:
        raise ValueError("At least two completed sessions are required.")
    if not isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("Initial cash must be finite and positive.")
    if (not weights or any(not isfinite(weight) or weight <= 0 for weight in weights.values())
            or not isclose(fsum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-12)):
        raise ValueError("Positive target weights must sum to one.")
    for previous, current in zip(sessions, sessions[1:]):
        if previous.day >= current.day:
            raise ValueError("Session dates must be unique and increasing.")
    for session in sessions:
        if session.market_open_at.utcoffset() is None or session.close_available_at.utcoffset() is None:
            raise ValueError("Decision and execution times must be timezone-aware.")
        if session.market_open_at >= session.close_available_at:
            raise ValueError("Close must be available after the opening event.")
        for ticker in weights:
            prices = session.prices.get(ticker)
            if prices is None or any(not isfinite(price) or price <= 0 for price in (prices.open, prices.close)):
                raise ValueError(f"Missing or invalid price for {ticker} on {session.day}.")
    for previous, current in zip(sessions, sessions[1:]):
        if previous.close_available_at >= current.market_open_at:
            raise ValueError("Previous close must be available before the next session opens.")


def _execute_at_open(
    batch: _OrderBatch, session: Session, positions: dict[str, float], cash: float, costs: Costs,
) -> tuple[float, tuple[Fill, ...], float]:
    """Apply sells first and scale all buys proportionally if cash is insufficient."""
    ordered = sorted(batch.quantities.items())
    fee_rate = costs.fee_bps / 10_000
    slippage_rate = costs.slippage_bps / 10_000
    cost_rate = fee_rate + slippage_rate
    opening_equity = cash + fsum(quantity * session.prices[ticker].open
                                 for ticker, quantity in positions.items())
    fills: list[Fill] = []

    def apply(ticker: str, requested: float, filled: float) -> None:
        nonlocal cash
        if filled == 0:
            return
        price = session.prices[ticker].open
        notional = abs(filled) * price
        fee, slippage = notional * fee_rate, notional * slippage_rate
        positions[ticker] += filled
        cash = fsum((cash, -price * filled, -fee, -slippage))
        fills.append(Fill(session.day, ticker, batch.decided_at, session.market_open_at,
                          requested, filled, price, fee, slippage))

    for ticker, quantity in ordered:
        if quantity < 0:
            apply(ticker, quantity, max(quantity, -positions[ticker]))
    cash_required = fsum(quantity * session.prices[ticker].open * (1 + cost_rate)
                         for ticker, quantity in ordered if quantity > 0)
    scale = min(1.0, max(cash, 0.0) / cash_required) if cash_required else 0.0
    for ticker, quantity in ordered:
        if quantity > 0:
            apply(ticker, quantity, quantity * scale)
    # Floating point roundoff can leave a tiny negative balance after scaling.
    if cash < -max(1e-8, opening_equity * 1e-12):
        raise ArithmeticError("Portfolio used more cash than was available.")
    return max(cash, 0.0), tuple(fills), fsum(fill.notional for fill in fills) / opening_equity


def simulate(
    sessions: Sequence[Session],
    weights: Mapping[str, float],
    *,
    initial_cash: float,
    costs: Costs,
    rebalance_monthly: bool = True,
) -> Simulation:
    """Submit fixed quantities at the first observed close of each month.

    With monthly rebalancing off, submit the initial allocation only. The
    closing signal sizes market orders for the following session. Closing
    positions are marked to market, with no forced final liquidation.
    """
    _validate_inputs(sessions, weights, initial_cash)
    cash = initial_cash
    positions = dict.fromkeys(sorted(weights), 0.0)
    pending: _OrderBatch | None = None
    last_month: tuple[int, int] | None = None
    points: list[PortfolioPoint] = []
    fills: list[Fill] = []
    turnover = 0.0
    for session in sessions:
        if pending is not None:
            cash, executed, traded = _execute_at_open(pending, session, positions, cash, costs)
            fills.extend(executed)
            turnover += traded
            pending = None
        equity = cash + fsum(quantity * session.prices[ticker].close
                             for ticker, quantity in positions.items())
        points.append(PortfolioPoint(session.day, equity, cash, positions.copy()))
        month = (session.day.year, session.day.month)
        if last_month is None or (rebalance_monthly and month != last_month):
            quantities = {
                ticker: equity * weights[ticker] / session.prices[ticker].close - positions[ticker]
                for ticker in positions
            }
            pending = _OrderBatch(session.close_available_at, quantities)
        last_month = month
    return Simulation(initial_cash, tuple(points), tuple(fills), turnover)
