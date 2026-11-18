from datetime import date
from decimal import Decimal
import io
import sys
from zipfile import ZipFile

import pytest

from quantedge_research.entitlements import itc_hotels_series
from quantedge_research.nse_raw import audit_raw_files, main, parse_raw_archive


def zipped(text):
    out = io.BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("report.csv", text)
    return out.getvalue()


@pytest.mark.parametrize(("header", "row", "session", "ticker", "series"), [
    ("TIMESTAMP,SYMBOL,SERIES,ISIN,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY",
     "13-FEB-2019,ITC,EQ,INE154A01025,100.05,104,99,102.25,900",
     date(2019, 2, 13), "ITC.NS", "EQ"),
    ("TradDt,TckrSymb,SctySrs,ISIN,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol",
     "2025-01-29,ITCHOTELS,BE,INE379A01028,100.05,104,99,102.25,900",
     date(2025, 1, 29), "ITCHOTELS.NS", itc_hotels_series(date(2025, 1, 29))),
])
def test_parses_unadjusted_cash_market_fields(header, row, session, ticker, series):
    evidence, (bar,) = parse_raw_archive(zipped(f"{header}\n{row}\n"), session, {ticker: series})
    assert evidence.present == (ticker,)
    assert (bar.open, bar.close, bar.volume, bar.series) == (Decimal("100.05"), Decimal("102.25"), 900, series)
    with pytest.raises(ValueError, match="Invalid raw OHLCV"):
        parse_raw_archive(zipped(f"{header}\n{row.replace(',104,', ',1,')}\n"), session, {ticker: series})


def test_private_raw_audit_never_silently_skips_missing_day(tmp_path):
    session = date(2019, 2, 13)
    report = audit_raw_files(tmp_path, (session,), {"ITC.NS": "EQ"})
    assert not report["coverage_complete"]
    assert report["missing_files"] == ["2019-02-13"]


def test_cli_rejects_holdout_date_before_opening_local_files(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", [
        "nse_raw", "--baseline", "research/approved-portfolio-v1.json",
        "--archive-dir", str(tmp_path), "--end-exclusive", "2026-11-01", "--session", "2025-01-29",
    ])
    with pytest.raises(SystemExit, match="2"):
        main()
