"""Yahoo daily history adapter for exploratory research."""

from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from .data import Instrument, REQUIRED_COLUMNS


def fetch_provider_history(instrument: Instrument, start: date, end: date, cache: Path) -> pd.DataFrame:
    """Preserve Yahoo's delivered columns and label bars by exchange-local session."""
    cache.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache))
    ticker = yf.Ticker(instrument.ticker)
    frame = ticker.history(start=start, end=end, actions=True, auto_adjust=False,
                           repair=False, timeout=20, raise_errors=True)
    reported_currency = ticker.history_metadata.get("currency")
    if reported_currency != instrument.currency:
        raise ValueError(f"Provider currency {reported_currency!r} does not match {instrument.currency}.")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None or frame.empty:
        raise ValueError("Provider did not supply dated, exchange-local history.")
    timezone = {"US": "America/New_York", "NSE": "Asia/Kolkata"}[instrument.market]
    frame.index = pd.Index(frame.index.tz_convert(timezone).strftime("%Y-%m-%d"), name="session")
    return frame.reset_index()


def fetch_history(instrument: Instrument, start: date, end: date, cache: Path) -> pd.DataFrame:
    frame = fetch_provider_history(instrument, start, end, cache)
    renamed = frame.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
        "Dividends": "cash_dividend", "Stock Splits": "split_ratio",
    }).copy()
    if "Capital Gains" in frame and frame["Capital Gains"].fillna(0).ne(0).any():
        raise ValueError("Capital gains distributions need an explicit source mapping.")
    renamed["split_ratio"] = renamed["split_ratio"].replace(0, 1)
    return renamed.loc[:, list(REQUIRED_COLUMNS)].reset_index(drop=True)
