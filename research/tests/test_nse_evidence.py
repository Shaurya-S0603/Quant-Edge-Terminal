from datetime import UTC, date, datetime, timedelta
import io
from zipfile import ZipFile

import pandas as pd
import pytest

from quantedge_research.data import REQUIRED_COLUMNS, Instrument, audit_bars, session_schedule
from quantedge_research.nse_archive import inspect_archive


def test_cash_market_overrides_use_exchange_local_hours_and_remove_holiday():
    for session, expected_open, expected_close in (
        (date(2019, 10, 27), "12:45", "13:45"),
        (date(2020, 11, 14), "12:45", "13:45"),
        (date(2025, 2, 1), "03:45", "10:00"),
        (date(2026, 2, 1), "03:45", "10:00"),
    ):
        end = session + timedelta(days=1)
        row = session_schedule("NSE", session, end).loc[pd.Timestamp(session)]
        assert row.market_open == pd.Timestamp(f"{session.isoformat()}T{expected_open}:00Z")
        assert row.market_close == pd.Timestamp(f"{session.isoformat()}T{expected_close}:00Z")
        assert session_schedule("US", session, end).empty
    assert session_schedule("NSE", date(2026, 1, 15), date(2026, 1, 16)).empty


def test_casts_holiday_bar_as_off_calendar_and_gates_special_close():
    bars = pd.DataFrame(
        [(session, 10, 11, 9, 10, 100, 1.0, 0.0) for session in ("2026-01-15", "2026-02-01")],
        columns=REQUIRED_COLUMNS,
    )
    instrument = Instrument("nse:test", "TEST.NS", "NSE", "INR")
    args = dict(
        provider="fixture", price_basis="raw", start=date(2026, 1, 15),
        boundary=date(2026, 2, 1), end=date(2026, 2, 2),
    )
    _, early = audit_bars(bars, instrument, as_of=datetime(2026, 2, 1, 10, 29, tzinfo=UTC), **args)
    clean, mature = audit_bars(
        bars, instrument, as_of=datetime(2026, 2, 1, 10, 30, tzinfo=UTC), **args,
    )
    assert early.holdout.missing == ("2026-02-01",)
    assert early.unfinished_rows == 1
    assert mature.holdout.missing == ()
    assert mature.off_calendar == ("2026-01-15",)
    assert clean.iloc[0]["available_at"] == pd.Timestamp("2026-02-01T10:30:00Z")
    assert mature.calendar.schedule_sha256 == early.calendar.schedule_sha256
    assert len(mature.calendar.circulars) == 2


def zipped(csv_text: str) -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("daily.csv", csv_text)
    return stream.getvalue()


@pytest.mark.parametrize(("header", "row", "format_name"), [
    ("TIMESTAMP,SYMBOL,SERIES,OPEN,CLOSE,TOTTRDQTY",
     "24-OCT-2025,NIFTYBEES,EQ,100,101,10", "legacy"),
    ("TradDt,TckrSymb,SctySrs,OpnPric,ClsPric,TtlTradgVol",
     "2025-10-24,NIFTYBEES,EQ,100,101,10", "UDiFF"),
])
def test_official_report_contains_ticker_presence_and_no_price_fields(header, row, format_name):
    payload = zipped(f"{header}\n{row}\n" + row.replace(",EQ,", ",BE,") + "\n")
    session = date(2025, 10, 24)
    report = inspect_archive(payload, session, {"NIFTYBEES.NS", "ITC.NS"})
    assert report.present == ("NIFTYBEES.NS",)
    assert report.missing == ("ITC.NS",)
    assert report.format == format_name
    assert len(report.archive_sha256) == 64
    assert set(vars(report)) == {"session", "source_url", "archive_sha256", "format", "present", "missing"}
    with pytest.raises(ValueError, match="different trading date"):
        inspect_archive(payload, date(2025, 10, 25), {"NIFTYBEES.NS"})
    with pytest.raises(ValueError, match="Duplicate"):
        inspect_archive(zipped(f"{header}\n{row}\n{row}\n"), session, {"NIFTYBEES.NS"})


def test_itc_demerger_is_flagged_even_when_bar_actions_look_complete():
    frame = pd.DataFrame(
        [("2025-01-06", 10, 11, 9, 10, 100, 1.0, 0.0)],
        columns=REQUIRED_COLUMNS,
    )
    _, audit = audit_bars(
        frame, Instrument("nse:itc", "ITC.NS", "NSE", "INR"),
        provider="fixture", price_basis="raw", start=date(2024, 12, 30),
        boundary=date(2025, 1, 1), end=date(2025, 1, 8),
        as_of=datetime(2025, 1, 9, tzinfo=UTC),
    )
    assert audit.split_count == audit.dividend_count == 0
    assert [action.kind for action in audit.unresolved_actions] == ["demerger_with_share_allotment"]
    assert audit.unresolved_actions[0].record_on == "2025-01-06"
