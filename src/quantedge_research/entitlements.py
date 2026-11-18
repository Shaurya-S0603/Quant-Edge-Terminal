"""Point-in-time valuation for a documented long-only share distribution."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Literal
from zoneinfo import ZoneInfo

from .session_overrides import NSE_TIMEZONE

ZERO = Decimal(0)
INDIA = ZoneInfo(NSE_TIMEZONE)


@dataclass(frozen=True)
class Distribution:
    parent_ticker: str
    child_ticker: str
    currency: str
    effective_on: date
    ex_date: date
    record_date: date
    allotted_on: date
    listed_on: date
    child_per_parent: Fraction

    def __post_init__(self) -> None:
        if not self.effective_on <= self.ex_date <= self.record_date <= self.allotted_on <= self.listed_on:
            raise ValueError("Distribution dates are out of sequence.")
        if self.parent_ticker == self.child_ticker or self.child_per_parent <= 0:
            raise ValueError("Expected distinct instruments and a positive distribution ratio.")


ITC_HOTELS = Distribution(
    parent_ticker="ITC.NS",
    child_ticker="ITCHOTELS.NS",
    currency="INR",
    effective_on=date(2025, 1, 1),
    ex_date=date(2025, 1, 6),
    record_date=date(2025, 1, 6),
    allotted_on=date(2025, 1, 11),
    listed_on=date(2025, 1, 29),
    child_per_parent=Fraction(1, 10),
)


def _local_day(timestamp: datetime) -> date:
    if timestamp.utcoffset() is None:
        raise ValueError("Supply timezone-aware availability timestamps.")
    return timestamp.astimezone(INDIA).date()


@dataclass(frozen=True)
class Entitlement:
    distribution: Distribution
    eligible_parent_shares: int

    def __post_init__(self) -> None:
        if type(self.eligible_parent_shares) is not int or self.eligible_parent_shares < 0:
            raise ValueError("Eligible settled parent shares must be a nonnegative integer.")

    @property
    def shares(self) -> Fraction:
        return self.eligible_parent_shares * self.distribution.child_per_parent


@dataclass(frozen=True)
class ChildMark:
    ticker: str
    currency: str
    kind: Literal["official_reference", "market"]
    session: date
    available_at: datetime
    price: Decimal
    source: str

    def __post_init__(self) -> None:
        if _local_day(self.available_at) < self.session:
            raise ValueError("A mark cannot be available before its session.")
        if self.kind not in {"official_reference", "market"}:
            raise ValueError("Unknown mark kind.")
        if not self.price.is_finite() or self.price <= ZERO or not self.source.strip():
            raise ValueError("Marks require a positive finite price and a source.")


@dataclass(frozen=True)
class FractionalPayment:
    available_at: datetime
    amount: Decimal
    currency: str
    source: str

    def __post_init__(self) -> None:
        _local_day(self.available_at)
        if not self.amount.is_finite() or self.amount < ZERO or not self.source.strip():
            raise ValueError("Specify sourced, nonnegative net cash proceeds.")


@dataclass(frozen=True)
class EntitlementValue:
    pending_whole_shares: int
    allotted_unlisted_shares: int
    listed_shares: int
    fractional_claim: Fraction
    cash_paid: Decimal
    claim_value: Decimal | None
    mark_kind: str | None

    @property
    def total_value(self) -> Decimal | None:
        return None if self.claim_value is None else self.cash_paid + self.claim_value


def value_entitlement(
    entitlement: Entitlement,
    as_of: datetime,
    *,
    marks: Iterable[ChildMark] = (),
    payment: FractionalPayment | None = None,
) -> EntitlementValue:
    """Value open entitlements only from facts available at the requested time.

    The caller supplies the pre-ex settled share count and real marks/payments.
    This function never generates fills or modifies the parent position.
    """
    day = _local_day(as_of)
    event = entitlement.distribution
    if day < event.ex_date or not entitlement.shares:
        return EntitlementValue(0, 0, 0, Fraction(0), ZERO, ZERO, None)

    whole = int(entitlement.shares)
    fraction = entitlement.shares - whole
    recognized_payment = ZERO
    if payment is not None and payment.available_at <= as_of:
        if not fraction or payment.currency != event.currency or _local_day(payment.available_at) < event.allotted_on:
            raise ValueError("Cash does not match an allotted fractional entitlement.")
        recognized_payment = payment.amount
        fraction = Fraction(0)

    pending = whole if day < event.allotted_on else 0
    unlisted = whole if event.allotted_on <= day < event.listed_on else 0
    listed = whole if day >= event.listed_on else 0
    open_shares = Fraction(whole) + fraction
    if not open_shares:
        return EntitlementValue(pending, unlisted, listed, fraction, recognized_payment, ZERO, None)

    kind = "official_reference" if day < event.listed_on else "market"
    candidates = [
        mark for mark in marks
        if mark.ticker == event.child_ticker and mark.currency == event.currency
        and mark.kind == kind and mark.available_at <= as_of
        and (event.ex_date <= mark.session < event.listed_on if kind == "official_reference"
             else event.listed_on <= mark.session)
    ]
    if not candidates:
        return EntitlementValue(pending, unlisted, listed, fraction, recognized_payment, None, None)
    latest = max((mark.session, mark.available_at) for mark in candidates)
    prices = {mark.price for mark in candidates if (mark.session, mark.available_at) == latest}
    if len(prices) != 1:
        raise ValueError("Conflicting marks at the latest availability timestamp.")
    per_share = prices.pop()
    claim_value = per_share * Decimal(open_shares.numerator) / Decimal(open_shares.denominator)
    return EntitlementValue(pending, unlisted, listed, fraction, recognized_payment, claim_value, kind)


def itc_hotels_series(session: date) -> str:
    """NSE series for valuation of distributed shares, outside the target basket."""
    if session < ITC_HOTELS.listed_on:
        raise ValueError("ITC Hotels had no traded mark before listing.")
    return "BE" if session < date(2025, 2, 11) else "EQ"
