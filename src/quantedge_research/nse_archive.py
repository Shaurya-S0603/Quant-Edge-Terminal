"""Check ticker coverage in official NSE cash-market archives without retaining bars."""

import argparse
from typing import BinaryIO
import csv
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from .baseline import load_baseline

ARCHIVE_HOST = "https://nsearchives.nseindia.com"
LEGACY_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
UDIFF_START = date(2024, 7, 8)
MAX_ZIP_BYTES = 8 * 1024 * 1024
MAX_CSV_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class ArchiveEvidence:
    session: str
    source_url: str
    archive_sha256: str
    format: str
    present: tuple[str, ...]
    missing: tuple[str, ...]


def _legacy_session(session: date) -> str:
    return f"{session.day:02d}-{LEGACY_MONTHS[session.month - 1]}-{session.year}"


def archive_url(session: date) -> str:
    if session < UDIFF_START:
        month = LEGACY_MONTHS[session.month - 1]
        name = f"cm{session.day:02d}{month}{session.year}bhav.csv.zip"
        return f"{ARCHIVE_HOST}/content/historical/EQUITIES/{session.year}/{month}/{name}"
    name = f"BhavCopy_NSE_CM_0_0_0_{session:%Y%m%d}_F_0000.csv.zip"
    return f"{ARCHIVE_HOST}/content/cm/{name}"


def inspect_archive(payload: bytes, session: date, tickers: set[str]) -> ArchiveEvidence:
    """Validate a single-date CSV and report selected EQ-series ticker presence."""
    if len(payload) > MAX_ZIP_BYTES:
        raise ValueError("NSE archive exceeds the compressed size limit.")
    if not tickers or any(not ticker.endswith(".NS") or ticker == ".NS" for ticker in tickers):
        raise ValueError("Expected one or more NSE tickers ending in .NS.")
    try:
        with ZipFile(io.BytesIO(payload)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != 1 or not members[0].filename.lower().endswith(".csv"):
                raise ValueError("Expected exactly one NSE CSV in the archive.")
            member = members[0]
            if member.file_size > MAX_CSV_BYTES:
                raise ValueError("NSE CSV exceeds the decompressed size limit.")
            with archive.open(member) as stream:
                return _inspect_csv(stream, payload, session, tickers)
    except BadZipFile as error:
        raise ValueError("Invalid NSE archive ZIP.") from error


def _inspect_csv(stream: BinaryIO, payload: bytes, session: date, tickers: set[str]) -> ArchiveEvidence:
    reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
    header = set(reader.fieldnames or ())
    if {"TradDt", "TckrSymb", "SctySrs", "OpnPric", "ClsPric", "TtlTradgVol"} <= header:
        format_name, date_column, ticker_column, series_column = "UDiFF", "TradDt", "TckrSymb", "SctySrs"
        expected_date = session.isoformat()
    elif {"TIMESTAMP", "SYMBOL", "SERIES", "OPEN", "CLOSE", "TOTTRDQTY"} <= header:
        format_name, date_column, ticker_column, series_column = "legacy", "TIMESTAMP", "SYMBOL", "SERIES"
        expected_date = _legacy_session(session)
    else:
        raise ValueError("Unexpected NSE cash-market CSV schema.")
    found: set[str] = set()
    saw_row = False
    for row in reader:
        saw_row = True
        if (row.get(date_column) or "").strip().upper() != expected_date:
            raise ValueError("NSE archive contains a different trading date.")
        if (row.get(series_column) or "").strip() != "EQ":
            continue
        ticker = (row.get(ticker_column) or "").strip() + ".NS"
        if ticker not in tickers:
            continue
        if ticker in found:
            raise ValueError(f"Duplicate NSE EQ row for {ticker}.")
        found.add(ticker)
    if not saw_row:
        raise ValueError("NSE archive contains no rows.")
    return ArchiveEvidence(
        session.isoformat(), archive_url(session), sha256(payload).hexdigest(),
        format_name, tuple(sorted(found)), tuple(sorted(tickers - found)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--session", type=date.fromisoformat, action="append", required=True)
    parser.add_argument("--archive-dir", type=Path, help="Use local official ZIPs instead of fetching.")
    args = parser.parse_args()
    sessions = sorted(set(args.session))
    if len(sessions) > 12:
        parser.error("Inspect at most 12 explicitly selected sessions per run.")
    if sessions[-1] >= date.today():
        parser.error("Only completed historical dates are supported.")
    baseline = load_baseline(args.baseline)
    tickers = {instrument.ticker for instrument in baseline.instruments if instrument.market == "NSE"}
    results = []
    for session in sessions:
        url = archive_url(session)
        if args.archive_dir:
            with (args.archive_dir / url.rsplit("/", 1)[-1]).open("rb") as stream:
                payload = stream.read(MAX_ZIP_BYTES + 1)
        else:
            request = Request(url, headers={"User-Agent": "QuantEdge/1.0 historical coverage audit"})
            with urlopen(request, timeout=15) as response:
                payload = response.read(MAX_ZIP_BYTES + 1)
        results.append(asdict(inspect_archive(payload, session, tickers)))
    print(json.dumps({"baseline_sha256": baseline.digest, "cash_market_coverage": results}, indent=2))


if __name__ == "__main__":
    main()
