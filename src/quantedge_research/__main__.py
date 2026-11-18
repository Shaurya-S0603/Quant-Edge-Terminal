"""Phase 1 CLI. Audit and proposal commands cannot approve or execute a holdout."""

import argparse
import csv
from datetime import UTC, date, datetime
import json
from pathlib import Path
import sys

from .baseline import load_baseline
from .data import Instrument, audit_bars, read_csv
from .split import Split


def coverage_report(args: argparse.Namespace) -> dict:
    split = Split.from_month_end(args.end_exclusive)
    now = datetime.now(UTC)
    if split.end_exclusive > now.date().replace(day=1):
        raise ValueError("Choose an end date after a completed month.")
    baseline = load_baseline(args.baseline) if args.baseline else None
    if baseline:
        if baseline.screening_end_exclusive > split.holdout_start:
            raise ValueError("The proposed holdout overlaps portfolio screening dates.")
        if baseline.screening_start < split.start:
            raise ValueError("Portfolio screening starts before the proposed development window.")
        instruments = baseline.instruments
    else:
        universe = args.universe or Path("research/starter-universe.csv")
        with universe.open(newline="", encoding="utf-8-sig") as stream:
            instruments = tuple(Instrument(**row) for row in csv.DictReader(stream))
    if not instruments or len({item.instrument_id for item in instruments}) != len(instruments):
        raise ValueError("Instrument IDs must be unique and the universe cannot be empty.")
    if len({(item.market, item.ticker) for item in instruments}) != len(instruments):
        raise ValueError("Market and ticker pairs must be unique.")
    rows, failures = [], []
    for instrument in instruments:
        try:
            if args.prices_dir is None:
                from .yahoo import fetch_history

                source = fetch_history(instrument, split.start, split.end_exclusive, args.cache_dir)
                basis = "provider_split_adjusted"
                provider = "Yahoo Finance via yfinance"
            else:
                path = (args.prices_dir / f"{instrument.ticker}.csv").resolve()
                if not path.is_relative_to(args.prices_dir.resolve()):
                    raise ValueError("Ticker resolves outside the input directory.")
                source = read_csv(path)
                basis = args.price_basis
                provider = args.source_name
            _, audit = audit_bars(
                source, instrument, provider=provider, price_basis=basis,
                start=split.start, boundary=split.holdout_start, end=split.end_exclusive, as_of=now,
            )
            rows.append(audit.report())
        except Exception as error:
            # Never emit provider payloads, headers, URLs or price observations.
            failures.append({"ticker": instrument.ticker, "error_type": type(error).__name__})
    return {
        "type": "unsealed_coverage_proposal",
        "generated_at": now.isoformat(),
        "split": split.dates(),
        "membership": "starter_list_without_point_in_time_history",
        "eligible_for_final_holdout": False,
        "limitations": [
            "Coverage audit only. No split approval was registered.",
            "Prior exposure, universe membership, delistings and action provenance require independent review.",
        ],
        "requested": len(instruments), "audits": rows, "failures": failures,
        **({"baseline": {"id": baseline.baseline_id, "sha256": baseline.digest}} if baseline else {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--universe", type=Path, help="Universe CSV. Defaults to the starter list.")
    source.add_argument("--baseline", type=Path, help="Versioned comparison portfolio JSON.")
    parser.add_argument("--end-exclusive", type=date.fromisoformat, required=True)
    parser.add_argument("--prices-dir", type=Path, help="Omit to query Yahoo once per symbol.")
    parser.add_argument("--source-name", default="local CSV files")
    parser.add_argument("--price-basis", choices=("raw", "provider_split_adjusted"), default="raw")
    parser.add_argument("--cache-dir", type=Path, default=Path(".data/research/provider-cache"))
    args = parser.parse_args()
    report = coverage_report(args)
    print(json.dumps(report, indent=2))
    return 0 if report["audits"] else 1


if __name__ == "__main__":
    sys.exit(main())
