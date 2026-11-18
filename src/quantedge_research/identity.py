"""Verified NSE split dates and daily-file identifier transitions."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class IdentifierTransition:
    ticker: str
    old_isin: str
    new_isin: str
    ex_date: date
    new_archive_isin_on: date
    units_per_old_unit: int
    source_urls: tuple[str, ...]

    def expected_archive_isin(self, session: date) -> str:
        return self.old_isin if session < self.new_archive_isin_on else self.new_isin


# The EQ file on the ex-date still showed the old ISIN for both instruments.
# These cutoffs map daily-file identifiers only. Apply splits on ex_date.
NSE_IDENTIFIER_TRANSITIONS = {
    item.ticker: item
    for item in (
        IdentifierTransition(
            "HDFCBANK.NS", "INE040A01026", "INE040A01034", date(2019, 9, 19),
            date(2019, 9, 20), 2,
            ("https://nsearchives.nseindia.com/content/circulars/CML41992.pdf",
             "https://nsearchives.nseindia.com/content/circulars/CMPT42091.pdf"),
        ),
        IdentifierTransition(
            "NIFTYBEES.NS", "INF732E01011", "INF204KB14I2", date(2019, 12, 19),
            date(2019, 12, 20), 10,
            ("https://archives.nseindia.com/content/circulars/CML42873.pdf",
             "https://archives.nseindia.com/content/circulars/CML42888.pdf",
             "https://nsearchives.nseindia.com/content/circulars/CMPT42889.pdf"),
        ),
    )
}
