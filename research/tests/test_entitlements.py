from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction

import pandas as pd
import pytest

from quantedge_research.data import total_return_index
from quantedge_research.entitlements import (
    ChildMark, Entitlement, FractionalPayment, ITC_HOTELS, itc_hotels_series, value_entitlement,
)


def moment(day, hour=12):
    return datetime(2025, 1, day, hour, tzinfo=UTC)


def mark(day, kind, price):
    return ChildMark("ITCHOTELS.NS", "INR", kind, date(2025, 1, day),
                     moment(day), Decimal(price), "synthetic")


def test_entitlement_values_only_available_marks_and_cash():
    entitlement = Entitlement(ITC_HOTELS, 105)
    assert entitlement.shares == Fraction(21, 2)
    reference = mark(6, "official_reference", "200")
    listed_mark = mark(29, "market", "190")
    payment = FractionalPayment(moment(31), Decimal("92.00"), "INR", "synthetic trustee receipt")
    inputs = dict(marks=[reference, listed_mark], payment=payment)
    assert value_entitlement(entitlement, moment(3), **inputs).total_value == 0
    before_publication = value_entitlement(entitlement, moment(6, 3), **inputs)
    assert before_publication.pending_whole_shares == 10
    assert before_publication.total_value is None
    pre_listing = value_entitlement(entitlement, moment(15), **inputs)
    assert pre_listing.allotted_unlisted_shares == 10
    assert pre_listing.listed_shares == 0 and pre_listing.total_value == Decimal("2100")
    before_first_mark = value_entitlement(entitlement, moment(29, 3), **inputs)
    assert before_first_mark.total_value is None
    listed = value_entitlement(entitlement, moment(29), **inputs)
    assert listed.listed_shares == 10 and listed.cash_paid == 0
    assert listed.total_value == Decimal("1995")
    paid = value_entitlement(entitlement, moment(31), **inputs)
    assert paid.fractional_claim == 0 and paid.cash_paid == Decimal("92")
    assert paid.total_value == Decimal("1992")


def test_fractional_only_receipt_does_not_require_a_traded_mark():
    entitlement = Entitlement(ITC_HOTELS, 9)
    paid = FractionalPayment(moment(31), Decimal("171"), "INR", "synthetic")
    assert value_entitlement(entitlement, moment(30), payment=paid).total_value is None
    result = value_entitlement(entitlement, moment(31), payment=paid)
    assert result.listed_shares == 0 and result.total_value == Decimal("171")


def test_itc_hotels_initial_series_and_plain_return_guard():
    assert itc_hotels_series(date(2025, 1, 29)) == "BE"
    assert itc_hotels_series(date(2025, 2, 11)) == "EQ"
    with pytest.raises(ValueError, match="before listing"):
        itc_hotels_series(date(2025, 1, 28))
    frame = pd.DataFrame({
        "instrument_id": ["nse:itc"] * 2, "ticker": ["ITC.NS"] * 2,
        "price_basis": ["raw"] * 2, "session": pd.to_datetime(["2025-01-03", "2025-01-06"]),
        "close": [100, 90], "split_ratio": [1, 1], "cash_dividend": [0, 0],
    })
    with pytest.raises(ValueError, match="share-entitlement"):
        total_return_index(frame)
