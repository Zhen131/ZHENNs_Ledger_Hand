"""Tests of the rule that a moment's offset from UTC is a whole number of minutes.

Some zones had offsets with seconds in them before the 1970s (Budapest was
at +01:16:20 in 1890). The ledger's way of writing a time cannot hold one, so
the check of a draft refuses such a moment and names the reason. A time known
only to the day carries no offset and is not affected. Every trade below is
invented.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import DraftProblems, Missing, Violation, check_draft

BUDAPEST = "Europe/Budapest"
NOW = datetime(2026, 10, 7, 9, 30, tzinfo=ZoneInfo(BUDAPEST))


def draft(occurred: OccurredTime, **changes: object) -> TradeDraft:
    made = TradeDraft(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        fee=Decimal("0"),
        occurred=occurred,
        raw_text="bought 0.02 BTC at 94900, no fee",
    )
    return dataclasses.replace(made, **changes)  # type: ignore[arg-type]


def old(zone: str, year: int, precision: TimePrecision = TimePrecision.MINUTE) -> OccurredTime:
    moment = datetime(year, 6, 1, 12, 0, 1 if precision is TimePrecision.SECOND else 0)
    return OccurredTime(moment.replace(tzinfo=ZoneInfo(zone)), precision, zone)


@pytest.mark.parametrize(
    ("zone", "year", "offset"),
    [
        (BUDAPEST, 1890, "+01:16:20"),
        ("Asia/Shanghai", 1900, "+08:05:43"),
        ("America/New_York", 1880, "-04:56:02"),
    ],
)
@pytest.mark.parametrize("precision", [TimePrecision.MINUTE, TimePrecision.SECOND])
def test_a_moment_whose_offset_has_seconds_is_refused_with_its_reason(
    zone: str, year: int, offset: str, precision: TimePrecision
) -> None:
    occurred = old(zone, year, precision)
    assert occurred.value.isoformat().endswith(offset)

    result = check_draft(draft(occurred), BUILT_IN_TABLE, NOW)

    assert result == DraftProblems(missing=(), violations=(Violation.OFFSET_HAS_SECONDS,))


def test_an_old_day_has_no_offset_and_is_accepted() -> None:
    day = OccurredTime(date(1890, 6, 1), TimePrecision.DAY, BUDAPEST)

    result = check_draft(draft(day), BUILT_IN_TABLE, NOW)

    assert isinstance(result, TradeRecord)
    assert result.occurred == day


@pytest.mark.parametrize(("zone", "year"), [(BUDAPEST, 1950), ("Asia/Kolkata", 1950)])
def test_an_old_moment_with_a_whole_minute_offset_is_accepted(zone: str, year: int) -> None:
    occurred = old(zone, year)
    offset = occurred.value.utcoffset()
    assert offset is not None
    assert not offset % timedelta(minutes=1)

    assert isinstance(check_draft(draft(occurred), BUILT_IN_TABLE, NOW), TradeRecord)


def test_the_offset_is_reported_with_every_other_problem() -> None:
    broken = draft(old(BUDAPEST, 1890), side=None, fee=Decimal("-1"))

    result = check_draft(broken, BUILT_IN_TABLE, NOW)

    assert result == DraftProblems(
        missing=(Missing.SIDE,),
        violations=(Violation.FEE_NEGATIVE, Violation.OFFSET_HAS_SECONDS),
    )
