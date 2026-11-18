"""Validate raw OHLCV from one consistent source, the NSE cash-market archive."""

import argparse
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

from .baseline import load_baseline
from .data import session_schedule
from .identity import NSE_IDENTIFIER_TRANSITIONS
from .nse_archive import ArchiveEvidence, MAX_ZIP_BYTES, archive_url, read_selected_rows
from .split import Split

FIELDS = {
    "legacy": ("OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY"),
    "UDiFF": ("OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol"),
}


@dataclass(frozen=True)
class RawBar:
    session: date
    ticker: str
    isin: str
    series: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def parse_raw_archive(
    payload: bytes, session: date, expected_series: Mapping[str, str],
) -> tuple[ArchiveEvidence, tuple[RawBar, ...]]:
    """Map both official schemas without adjusting prices or inventing actions."""
    evidence, rows = read_selected_rows(payload, session, expected_series)
    names = FIELDS[evidence.format]
    output: list[RawBar] = []
    for ticker, row in sorted(rows.items()):
        isin = (row.get("ISIN") or "").strip()
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
            raise ValueError(f"Missing or invalid ISIN for {ticker}.")
        try:
            open_, high, low, close = (Decimal((row.get(key) or "").strip()) for key in names[:4])
            size_text = (row.get(names[4]) or "").strip()
            if not re.fullmatch(r"[0-9]{1,19}", size_text):
                raise ValueError(f"Invalid whole-share volume for {ticker}.")
            volume = int(size_text)
        except InvalidOperation as error:
            raise ValueError(f"Invalid numeric OHLC for {ticker}.") from error
        if (any(not price.is_finite() or price <= 0 for price in (open_, high, low, close))
                or high < max(open_, low, close) or low > min(open_, close) or volume >= 2**63):
            raise ValueError(f"Invalid raw OHLCV for {ticker}.")
        output.append(RawBar(session, ticker, isin, expected_series[ticker],
                             open_, high, low, close, volume))
    return evidence, tuple(output)


def audit_raw_files(
    directory: Path, sessions: tuple[date, ...], expected_series: Mapping[str, str],
) -> dict:
    evidence_rows: list[dict] = []
    missing_files: list[str] = []
    failures: list[dict] = []
    identifiers: dict[str, set[str]] = {ticker: set() for ticker in sorted(expected_series)}
    identifier_mismatches: list[dict[str, str]] = []
    for session in sessions:
        filename = archive_url(session).rsplit("/", 1)[-1]
        try:
            with (directory / filename).open("rb") as stream:
                payload = stream.read(MAX_ZIP_BYTES + 1)
            evidence, bars = parse_raw_archive(payload, session, expected_series)
        except FileNotFoundError:
            missing_files.append(session.isoformat())
            continue
        except (OSError, ValueError) as error:
            failures.append({"session": session.isoformat(), "reason": str(error)})
            continue
        evidence_rows.append(asdict(evidence) | {"zero_volume": [b.ticker for b in bars if b.volume == 0]})
        for bar in bars:
            identifiers[bar.ticker].add(bar.isin)
            transition = NSE_IDENTIFIER_TRANSITIONS.get(bar.ticker)
            if transition is not None:
                expected_isin = transition.expected_archive_isin(session)
                if bar.isin != expected_isin:
                    identifier_mismatches.append({
                        "ticker": bar.ticker, "session": session.isoformat(),
                        "observed": bar.isin, "expected": expected_isin,
                    })
    conflicted = {row["ticker"] for row in identifier_mismatches}
    resolved = []
    unresolved = {}
    for ticker, isins in identifiers.items():
        if len(isins) < 2:
            continue
        transition = NSE_IDENTIFIER_TRANSITIONS.get(ticker)
        if (transition is not None and ticker not in conflicted
                and isins == {transition.old_isin, transition.new_isin}):
            resolved.append({
                **asdict(transition),
                "ex_date": transition.ex_date.isoformat(),
                "new_archive_isin_on": transition.new_archive_isin_on.isoformat(),
            })
        else:
            unresolved[ticker] = sorted(isins)
    return {
        "source": "NSE cash market daily archives",
        "price_basis": "raw",
        "expected_sessions": len(sessions),
        "validated_sessions": len(evidence_rows),
        "coverage_complete": bool(sessions) and len(evidence_rows) == len(sessions)
        and not any(row["missing"] for row in evidence_rows),
        "missing_files": missing_files,
        "failed_sessions": failures,
        "sessions": evidence_rows,
        "resolved_identifier_changes": resolved,
        "identity_consistent": not unresolved and not identifier_mismatches,
        "unresolved_identifier_changes": unresolved,
        "identifier_mismatches": identifier_mismatches,
        "identifier_changes": {
            ticker: sorted(values) for ticker, values in identifiers.items() if len(values) > 1
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--end-exclusive", type=date.fromisoformat, required=True,
                        help="Exclusive end of the proposed ten-year window.")
    parser.add_argument(
        "--custodian-full-window", action="store_true",
        help="Report metadata for the entire proposed window from private authorized local files.",
    )
    parser.add_argument("--session", type=date.fromisoformat, action="append",
                        help="Validate explicitly selected development sessions. Default: all development sessions.")
    args = parser.parse_args()
    split = Split.from_month_end(args.end_exclusive)
    baseline = load_baseline(args.baseline)
    if split.end_exclusive > date.today().replace(day=1):
        parser.error("Choose an end date after a completed month.")
    if not split.start <= baseline.screening_start < baseline.screening_end_exclusive <= split.holdout_start:
        parser.error("Portfolio screening dates must fit within development.")
    # Before the split is sealed, expanding the proposed end must not expose
    # the window already reserved by this baseline for evaluation.
    available_end = (split.end_exclusive if args.custodian_full_window
                     else min(split.holdout_start, baseline.screening_end_exclusive))
    calendar = session_schedule("NSE", split.start, available_end)
    expected = tuple(session.date() for session in calendar.index)
    sessions = tuple(sorted(set(args.session))) if args.session else expected
    if not set(sessions) <= set(expected):
        parser.error("Use trading sessions inside the selected audit window. Holdout files are excluded by default.")
    tickers = {i.ticker: "EQ" for i in baseline.instruments if i.market == "NSE"}
    report = audit_raw_files(args.archive_dir, sessions, tickers)
    report["baseline_sha256"] = baseline.digest
    report["audit_bounds"] = [split.start.isoformat(), available_end.isoformat()]
    report["scope"] = "custodian_full_window_metadata" if args.custodian_full_window else "development_metadata"
    report["all_window_sessions_requested"] = sessions == expected
    print(json.dumps(report, indent=2))
    return 0 if report["coverage_complete"] and report["identity_consistent"] else 1


if __name__ == "__main__":
    sys.exit(main())
