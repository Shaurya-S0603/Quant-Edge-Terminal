"""Verify ITC entitlement inputs from private archives and emit metadata only."""

import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path

from .entitlements import ITC_HOTELS, itc_hotels_series
from .nse_archive import MAX_ZIP_BYTES, archive_url
from .nse_raw import parse_raw_archive

PRE_EX = date(2025, 1, 3)
FIRST_EQ = date(2025, 2, 11)
PARENT_SPREAD_SOURCES = (
    "https://nsearchives.nseindia.com/content/circulars/CMTR65845.pdf",
    "https://www.niftyindices.com/Press_Release/ind_prs26042023.pdf",
)
FRACTIONAL_SOURCE = "https://www.itchotels.com/dividend-iepf"


def verify_itc_archive_inputs(directory: Path) -> dict:
    """Reconcile archive rows for the event without exporting holdout prices."""
    cases = (
        (PRE_EX, ITC_HOTELS.parent_ticker, "EQ"),
        (ITC_HOTELS.ex_date, ITC_HOTELS.parent_ticker, "EQ"),
        (ITC_HOTELS.listed_on, ITC_HOTELS.child_ticker, itc_hotels_series(ITC_HOTELS.listed_on)),
        (FIRST_EQ, ITC_HOTELS.child_ticker, itc_hotels_series(FIRST_EQ)),
    )
    records = {}
    evidence_rows = []
    for session, ticker, series in cases:
        url = archive_url(session)
        with (directory / url.rsplit("/", 1)[-1]).open("rb") as stream:
            payload = stream.read(MAX_ZIP_BYTES + 1)
        evidence, bars = parse_raw_archive(payload, session, {ticker: series})
        if len(bars) != 1 or bars[0].volume <= 0:
            raise ValueError(f"No validated traded {series} record for {ticker} on {session}.")
        bar = bars[0]
        records[session] = bar
        evidence_rows.append({
            "session": session.isoformat(), "ticker": ticker, "series": series, "isin": bar.isin,
            "archive_sha256": evidence.archive_sha256, "source_url": evidence.source_url,
        })
    before = records[PRE_EX]
    after = records[ITC_HOTELS.ex_date]
    listed = records[ITC_HOTELS.listed_on]
    rolling = records[FIRST_EQ]
    if before.isin != after.isin or listed.isin != rolling.isin or before.isin == listed.isin:
        raise ValueError("Unexpected parent or child identifier across the event.")
    ratio = ITC_HOTELS.child_per_parent
    derived = (before.close - after.open) * Decimal(ratio.denominator) / Decimal(ratio.numerator)
    if derived <= 0:
        raise ValueError("Archive open implies a nonpositive child reference.")
    return {
        "scope": "custodian_entitlement_metadata",
        "records": evidence_rows,
        "prelisting_reference": {
            "status": "positive_archive_derivation",
            "method": "Divide the last cum-entitlement parent close minus ex-day parent open by the child-per-parent ratio.",
            "sources": PARENT_SPREAD_SOURCES,
            "requires": "Explicitly verify auction result identity and intraday availability from a historical source before using the mark.",
        },
        "market_marks": {"status": "listing_and_first_EQ_session_validated",
                         "full_child_series_validated": False},
        "fractional_settlement": {
            "status": "mechanism_confirmed_net_amount_and_credit_timestamp_unverified",
            "source_url": FRACTIONAL_SOURCE,
        },
        "eligible_for_holdout": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, required=True,
                        help="Private directory of authorized copies of the four dated NSE ZIPs.")
    args = parser.parse_args()
    print(json.dumps(verify_itc_archive_inputs(args.archive_dir), indent=2))


if __name__ == "__main__":
    main()
