"""Issuer-confirmed events requiring treatment beyond the raw bar schema."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ComplexAction:
    ticker: str
    effective_on: str
    record_on: str
    kind: str
    source_url: str


EVENTS = (
    ComplexAction(
        "ITC.NS", "2025-01-01", "2025-01-06", "demerger_with_share_allotment",
        "https://itcportal.com/content/dam/itc-corporate/pdfs/report-and-accounts/ITC-Report-and-Accounts-2025.pdf",
    ),
)


def known_complex_actions(ticker: str, start: date, end: date) -> tuple[ComplexAction, ...]:
    begin, stop = start.isoformat(), end.isoformat()
    return tuple(
        event for event in EVENTS if event.ticker == ticker
        and (begin <= event.effective_on < stop or begin <= event.record_on < stop)
    )
