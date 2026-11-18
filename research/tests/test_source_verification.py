from datetime import date
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from quantedge_research.entitlement_evidence import verify_itc_archive_inputs
from quantedge_research.identity import NSE_IDENTIFIER_TRANSITIONS
from quantedge_research.nse_archive import archive_url
from quantedge_research.nse_raw import audit_raw_files


def put_zip(directory, session, csv_text):
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("report.csv", csv_text)
    (directory / archive_url(session).rsplit("/", 1)[1]).write_bytes(payload.getvalue())


@pytest.mark.parametrize("ticker", ["HDFCBANK.NS", "NIFTYBEES.NS"])
def test_known_split_and_identifier_change_are_separate(tmp_path, ticker):
    change = NSE_IDENTIFIER_TRANSITIONS[ticker]
    session_pair = (change.ex_date, change.new_archive_isin_on)
    header = "TIMESTAMP,SYMBOL,SERIES,ISIN,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY"
    for day, isin in zip(session_pair, (change.old_isin, change.new_isin), strict=True):
        row = f"{day:%d-%b-%Y},{ticker.removesuffix('.NS')},EQ,{isin},100,101,99,100,200"
        put_zip(tmp_path, day, header + "\n" + row + "\n")
    result = audit_raw_files(tmp_path, session_pair, {ticker: "EQ"})
    assert result["identity_consistent"]
    assert result["resolved_identifier_changes"][0]["ex_date"] != result["resolved_identifier_changes"][0]["new_archive_isin_on"]
    assert change.units_per_old_unit == (2 if ticker == "HDFCBANK.NS" else 10)
    assert result["resolved_identifier_changes"][0]["units_per_old_unit"] == change.units_per_old_unit
    day = change.ex_date
    row = f"{day:%d-%b-%Y},{ticker.removesuffix('.NS')},EQ,{change.new_isin},100,101,99,100,200"
    put_zip(tmp_path, day, header + "\n" + row + "\n")
    result = audit_raw_files(tmp_path, session_pair, {ticker: "EQ"})
    assert not result["identity_consistent"] and result["identifier_mismatches"][0]["session"] == day.isoformat()


def test_private_entitlement_report_leaves_values_and_unverified_cash_out(tmp_path):
    header = "TradDt,TckrSymb,SctySrs,ISIN,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol"
    for iso, ticker, series, isin, price in (
        ("2025-01-03", "ITC", "EQ", "INE154A01025", "517.45"),
        ("2025-01-06", "ITC", "EQ", "INE154A01025", "490.10"),
        ("2025-01-29", "ITCHOTELS", "BE", "INE379A01028", "187.50"),
        ("2025-02-11", "ITCHOTELS", "EQ", "INE379A01028", "189.50"),
    ):
        row = f"{iso},{ticker},{series},{isin}," + ",".join([price] * 4) + ",200"
        put_zip(tmp_path, date.fromisoformat(iso), header + "\n" + row + "\n")
    result = verify_itc_archive_inputs(tmp_path)
    assert result["market_marks"]["status"] == "listing_and_first_EQ_session_validated"
    assert result["prelisting_reference"]["status"] == "positive_archive_derivation"
    assert "unverified" in result["fractional_settlement"]["status"]
    assert not result["eligible_for_holdout"]
    assert not any(str(price) in json.dumps(result) for price in ("517.45", "490.10", "187.50", "189.50"))
