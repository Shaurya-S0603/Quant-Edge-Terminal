from datetime import UTC, date, datetime

import pandas as pd
import pytest

from quantedge_research.data import Instrument, audit_bars, total_return_index
from quantedge_research.split import Split, fit_label_is_eligible


def test_exact_split_dates_and_forward_label_purging():
    split = Split.from_month_end(date(2026, 11, 1))
    assert split.dates() == {
        "start": "2016-11-01", "holdout_start": "2024-11-01", "end_exclusive": "2026-11-01"
    }
    decision, maturity, boundary = [datetime(2024, 11, d, tzinfo=UTC) for d in (1, 2, 3)]
    assert fit_label_is_eligible(decision, maturity, boundary)
    assert not fit_label_is_eligible(decision, boundary, boundary)
    assert not fit_label_is_eligible(boundary, maturity, boundary)
    with pytest.raises(ValueError):
        fit_label_is_eligible(decision.replace(tzinfo=None), maturity, boundary)


def test_audit_drops_closed_sessions_duplicates_bad_bars_and_incomplete_bar():
    frame = pd.DataFrame(
        [(session, 10, high, 9, 10, 100, 1.0, 0.0)
         for session, high in [
             ("2024-11-27", 11), ("2024-11-28", 11), ("2024-11-29", 11),
             ("2024-11-29", 11), ("2024-12-02", 9), ("2024-12-03", 11),
             ("2024-12-04", 11), ("2024-2-4", 11),
         ]],
        columns=["session", "open", "high", "low", "close", "volume", "split_ratio", "cash_dividend"],
    )
    clean, audit = audit_bars(
        frame, Instrument("sec-1", "TEST", "US", "USD"), provider="fixture", price_basis="raw",
        start=date(2024, 11, 27), boundary=date(2024, 12, 1), end=date(2024, 12, 5),
        as_of=datetime(2024, 12, 4, 20, tzinfo=UTC),
    )
    assert audit.development.missing == ("2024-11-29",)
    assert audit.holdout.missing == ("2024-12-02", "2024-12-04")
    assert audit.off_calendar == ("2024-11-28",)
    assert (audit.invalid_rows, audit.duplicate_rows, audit.unfinished_rows) == (2, 2, 1)
    assert clean.iloc[-1]["available_at"] == pd.Timestamp("2024-12-03T21:30:00Z")


def test_split_and_dividend_adjustment_is_prefix_invariant():
    bars = pd.DataFrame({
        "instrument_id": ["s"] * 4,
        "price_basis": ["raw"] * 4,
        "session": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
        "close": [100.0, 50.0, 49.0, 60.0],
        "split_ratio": [1.0, 2.0, 1.0, 1.0],
        "cash_dividend": [0.0, 0.0, 1.0, 0.0],
    })
    pd.testing.assert_series_equal(total_return_index(bars).iloc[:3], total_return_index(bars.iloc[:3]))
    assert list(total_return_index(bars.iloc[:3])) == [1.0, 1.0, 1.0]
    with pytest.raises(ValueError, match="raw"):
        total_return_index(bars.assign(price_basis="provider_split_adjusted"))
