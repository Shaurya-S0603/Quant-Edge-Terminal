"""Historical daily-bar ingestion and exchange-session validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import pandas_market_calendars as calendars

from .action_review import ComplexAction, known_complex_actions
from .session_overrides import NSE_TIMEZONE, overrides_for

MARKETS = {"US": ("NYSE", "USD"), "NSE": ("NSE", "INR")}
BAR_COLUMNS = ("open", "high", "low", "close", "volume")
ACTION_COLUMNS = ("split_ratio", "cash_dividend")
PriceBasis = Literal["raw", "provider_split_adjusted"]
REQUIRED_COLUMNS = ("session", *BAR_COLUMNS, *ACTION_COLUMNS)


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    ticker: str
    market: str
    currency: str
    role: str = "equity"

    def __post_init__(self) -> None:
        if self.market not in MARKETS or self.currency != MARKETS[self.market][1]:
            raise ValueError(f"Market and currency disagree for {self.ticker}.")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise ValueError("Instrument ID and ticker are required.")
        if self.role not in {"equity", "benchmark"}:
            raise ValueError("Instrument role must be equity or benchmark.")


@dataclass(frozen=True)
class Coverage:
    expected: int
    observed: int
    first: str | None
    last: str | None
    missing: tuple[str, ...]


@dataclass(frozen=True)
class CalendarEvidence:
    reference: str
    version: str
    schedule_sha256: str
    circulars: tuple[str, ...]


@dataclass(frozen=True)
class Audit:
    instrument: Instrument
    provider: str
    audited_at: str
    bounds: tuple[str, str, str]
    price_basis: PriceBasis
    calendar: CalendarEvidence
    development: Coverage
    holdout: Coverage
    off_calendar: tuple[str, ...]
    invalid_rows: int
    duplicate_rows: int
    zero_volume_rows: int
    split_count: int
    dividend_count: int
    unfinished_rows: int
    unresolved_actions: tuple[ComplexAction, ...]

    def report(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=16)
def session_schedule(market: str, start: date, end: date) -> pd.DataFrame:
    """Exchange-local session labels with UTC market open and close."""
    if not start < end:
        raise ValueError("The schedule must span a positive date range.")
    name = MARKETS[market][0]
    schedule = calendars.get_calendar(name).schedule(start, end - timedelta(days=1))
    # pandas may return different datetime precisions for an empty schedule.
    # Explicit UTC columns keep insertions valid even for a single weekend date.
    schedule = schedule[["market_open", "market_close"]].astype("datetime64[ns, UTC]")
    for item in overrides_for(market, start, end):
        label = pd.Timestamp(item.session)
        if item.is_closed:
            schedule = schedule.drop(label, errors="ignore")
        else:
            assert item.normal_open is not None and item.normal_close is not None
            market_open = pd.Timestamp(datetime.combine(item.session, item.normal_open),
                                       tz=NSE_TIMEZONE).tz_convert("UTC")
            market_close = pd.Timestamp(datetime.combine(item.session, item.normal_close),
                                        tz=NSE_TIMEZONE).tz_convert("UTC")
            schedule.loc[label] = (market_open, market_close)
    return schedule.sort_index()


def _calendar_evidence(market: str, start: date, end: date, schedule: pd.DataFrame) -> CalendarEvidence:
    canonical = schedule.to_csv(index_label="session", date_format="%Y-%m-%dT%H:%M:%S%z",
                                lineterminator="\n")
    return CalendarEvidence(
        reference=MARKETS[market][0],
        version=calendars.__version__,
        schedule_sha256=sha256(canonical.encode()).hexdigest(),
        circulars=tuple(item.source_url for item in overrides_for(market, start, end)),
    )


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"session": "str"})


def audit_bars(
    source: pd.DataFrame,
    instrument: Instrument,
    *,
    provider: str,
    price_basis: PriceBasis,
    start: date,
    boundary: date,
    end: date,
    as_of: datetime,
) -> tuple[pd.DataFrame, Audit]:
    """Isolate bad rows and record why they were excluded. Never fill gaps."""
    if not start < boundary < end or as_of.utcoffset() is None:
        raise ValueError("Provide ordered dates and a timezone-aware as_of.")
    if price_basis not in {"raw", "provider_split_adjusted"}:
        raise ValueError("Unsupported price basis.")
    if not source.columns.is_unique or not set(REQUIRED_COLUMNS) <= set(source.columns):
        raise ValueError(f"Missing or duplicate columns. Expected {REQUIRED_COLUMNS!r}.")
    bars = source.loc[:, list(REQUIRED_COLUMNS)].copy()
    labels = bars["session"].astype("string")
    iso = labels.str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)
    bars["session"] = pd.to_datetime(labels.where(iso), format="%Y-%m-%d", errors="coerce")
    malformed_dates = int(bars["session"].isna().sum())
    bars = bars.loc[bars["session"].between(pd.Timestamp(start), pd.Timestamp(end), inclusive="left")]
    schedule = session_schedule(instrument.market, start, end)
    off_calendar = bars.loc[~bars["session"].isin(schedule.index), "session"]
    duplicates = bars["session"].duplicated(keep=False)
    for field in (*BAR_COLUMNS, *ACTION_COLUMNS):
        bars[field] = pd.to_numeric(bars[field], errors="coerce")
    finite = np.isfinite(bars[[*BAR_COLUMNS, *ACTION_COLUMNS]].to_numpy(dtype=float)).all(axis=1)
    valid = (
        finite
        & (bars[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (bars["high"] >= bars[["open", "close", "low"]].max(axis=1))
        & (bars["low"] <= bars[["open", "close"]].min(axis=1))
        & (bars["volume"] >= 0)
        & (bars["volume"] < 2**63)
        & (bars["volume"] % 1 == 0)
        & (bars["split_ratio"] > 0)
        & (bars["cash_dividend"] >= 0)
    )
    bars["open_at"] = bars["session"].map(schedule["market_open"])
    bars["available_at"] = bars["session"].map(schedule["market_close"]) + pd.Timedelta(minutes=30)
    unfinished = bars["available_at"] > pd.Timestamp(as_of)
    clean = bars.loc[valid & ~duplicates & ~unfinished & bars["available_at"].notna()].copy()
    clean["volume"] = clean["volume"].astype("int64")
    clean["instrument_id"] = instrument.instrument_id
    clean["ticker"] = instrument.ticker
    clean["market"] = instrument.market
    clean["currency"] = instrument.currency
    clean["price_basis"] = price_basis
    clean = clean.sort_values("session").reset_index(drop=True)

    def coverage(begin: date, stop: date) -> Coverage:
        expected = schedule.index[(schedule.index >= pd.Timestamp(begin)) & (schedule.index < pd.Timestamp(stop))]
        observed = pd.DatetimeIndex(clean.loc[
            clean["session"].between(pd.Timestamp(begin), pd.Timestamp(stop), inclusive="left"), "session"
        ])
        return Coverage(
            len(expected), len(observed),
            observed[0].date().isoformat() if len(observed) else None,
            observed[-1].date().isoformat() if len(observed) else None,
            tuple(ts.date().isoformat() for ts in expected.difference(observed)),
        )

    return clean, Audit(
        instrument, provider, as_of.isoformat(),
        (start.isoformat(), boundary.isoformat(), end.isoformat()), price_basis,
        _calendar_evidence(instrument.market, start, end, schedule),
        coverage(start, boundary), coverage(boundary, end),
        tuple(sorted(set(off_calendar.dt.strftime("%Y-%m-%d")))),
        malformed_dates + int((~valid).sum()), int(duplicates.sum()),
        int(clean["volume"].eq(0).sum()), int(clean["split_ratio"].ne(1).sum()),
        int(clean["cash_dividend"].ne(0).sum()), int(unfinished.sum()),
        known_complex_actions(instrument.ticker, start, end),
    )


def total_return_index(bars: pd.DataFrame) -> pd.Series:
    """Causal close-to-close index for verified raw bars with effective actions.

    Ratio is new shares per prior share. Dividends are per post-split share.
    Incomplete session sequences, price-only adjustments, and missing action
    records must be resolved in the source audit before using this index.
    """
    if bars.empty or bars["instrument_id"].nunique() != 1 or not bars["price_basis"].eq("raw").all():
        raise ValueError("Use verified raw history for one instrument.")
    if not bars["session"].is_monotonic_increasing or bars["session"].duplicated().any():
        raise ValueError("Sessions must be unique and ordered.")
    if "ticker" in bars.columns:
        ticker = bars["ticker"].iloc[0]
        start = bars["session"].iloc[0].date()
        end = bars["session"].iloc[-1].date() + timedelta(days=1)
        if known_complex_actions(ticker, start, end):
            raise ValueError("Use share-entitlement accounting for this corporate-action window.")
    gross = bars["split_ratio"] * (bars["close"] + bars["cash_dividend"]) / bars["close"].shift()
    gross.iloc[0] = 1.0
    return gross.cumprod().rename("total_return_index")
