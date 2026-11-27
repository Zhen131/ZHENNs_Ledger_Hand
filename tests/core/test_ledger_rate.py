"""Tests of reading the ledger's exchange rates, picking one and comparing a rate with it.

Every rate, day and identifier is invented. The trade is on 2026-11-20,
paid in EUR for an asset priced in USD, its rate 1.08, unless a test says
otherwise.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_rate import (
    LONG_AGO_DAYS,
    LedgerRateNote,
    LedgerRateOutcome,
    RateRow,
    gap_in_a_hundred,
    pick,
    rate_gap,
    read_rate,
    row_day,
)

EUR, USD, GBP = "asset-eur", "asset-usd", "asset-gbp"
DAY = date(2026, 11, 20)


def row(
    base: str,
    quote: str,
    rate: str,
    day: str,
    source: str = "manual",
    online: str | None = None,
) -> RateRow:
    return RateRow(
        base_id=base,
        base_code=base.removeprefix("asset-").upper(),
        quote_id=quote,
        quote_code=quote.removeprefix("asset-").upper(),
        rate=rate,
        rate_date=day,
        source=source,
        online_source=online,
    )


def gap_of(rate: str, one: RateRow) -> Decimal:
    picked, _ = pick([one], EUR, USD, DAY)
    assert picked is not None
    return rate_gap(Decimal(rate), picked)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", "0", "0.000", "-1", "abc", ""])
def test_a_rate_that_is_not_a_finite_decimal_above_zero_does_not_read(text: str) -> None:
    assert read_rate(text) is None


def test_a_rate_reads_as_it_was_written() -> None:
    assert read_rate("1.08") == Decimal("1.08")
    assert read_rate("0.925000") == Decimal("0.925")


def test_a_day_reads_from_the_first_ten_characters_as_the_ledger_reads_it() -> None:
    assert row_day("2026-11-20") == DAY
    assert row_day("2026-11-20T10:00:00+01:00") == DAY
    assert row_day("20.11.2026") is None
    assert row_day("2026-13-01") is None
    assert row_day("") is None


def test_a_row_the_same_way_round_is_compared_as_it_is() -> None:
    picked, passed = pick([row(EUR, USD, "1.08", "2026-11-20")], EUR, USD, DAY)

    assert picked is not None and not picked.inverted and passed == 0
    assert picked.converted == Decimal("1.08")
    assert rate_gap(Decimal("1.08"), picked) == 0


def test_a_row_the_other_way_round_is_multiplied_and_said_as_its_inverse() -> None:
    picked, _ = pick([row(USD, EUR, "0.925", "2026-11-19", "online", "frankfurter")], EUR, USD, DAY)

    assert picked is not None and picked.inverted
    assert str(picked.converted) == "1.0810810811"
    assert rate_gap(Decimal("1.08"), picked) == Decimal("0.001")
    assert gap_in_a_hundred(rate_gap(Decimal("1.08"), picked)) == Decimal("0.1")


def test_a_far_rate_is_the_gap_over_the_ledgers_rate() -> None:
    gap = gap_of("1.08", row(EUR, USD, "1.30", "2026-11-20"))

    assert gap > Decimal("0.1")
    assert gap_in_a_hundred(gap) == Decimal("16.9")
    assert gap_in_a_hundred(gap_of("1.08", row(EUR, USD, "1.17", "2026-11-20"))) == Decimal("7.7")


def test_exactly_ten_in_a_hundred_both_ways_round_is_exactly_the_share() -> None:
    assert gap_of("1.08", row(EUR, USD, "1.2", "2026-11-20")) == Decimal("0.1")
    assert gap_of("1.25", row(USD, EUR, "0.88", "2026-11-20")) == Decimal("0.1")


def test_only_rows_not_after_the_day_count_and_the_latest_wins() -> None:
    rows = [
        row(EUR, USD, "1.5", "2026-11-25"),
        row(EUR, USD, "1.09", "2026-11-18"),
        row(EUR, USD, "1.07", "2026-11-05"),
    ]

    picked, _ = pick(rows, EUR, USD, DAY)

    assert picked is not None and picked.rate == Decimal("1.09")
    assert pick([rows[0]], EUR, USD, DAY) == (None, 0)


def test_on_one_day_a_rate_typed_in_wins_over_one_fetched() -> None:
    rows = [
        row(USD, EUR, "0.9", "2026-11-20", "online", "frankfurter"),
        row(EUR, USD, "1.08", "2026-11-20"),
    ]

    picked, _ = pick(rows, EUR, USD, DAY)

    assert picked is not None and picked.row.by_hand and picked.rate == Decimal("1.08")


def test_rows_of_other_moneys_are_never_picked_and_one_is_never_taken_instead() -> None:
    picked, passed = pick([row(EUR, GBP, "0.86", "2026-11-20")], EUR, USD, DAY)

    assert picked is None and passed == 0


@pytest.mark.parametrize("text", ["NaN", "Infinity", "0", "-1", "one point oh eight"])
def test_a_row_whose_rate_does_not_read_is_passed_over_and_counted(text: str) -> None:
    rows = [row(EUR, USD, text, "2026-11-20"), row(EUR, USD, "1.07", "2026-11-19")]

    picked, passed = pick(rows, EUR, USD, DAY)

    assert picked is not None and picked.rate == Decimal("1.07") and passed == 1
    assert pick(rows[:1], EUR, USD, DAY) == (None, 1)


def test_a_row_whose_day_does_not_read_is_passed_over_and_counted() -> None:
    picked, passed = pick([row(EUR, USD, "1.08", "yesterday")], EUR, USD, DAY)

    assert picked is None and passed == 1


def test_the_eight_fields_are_kept_under_the_ledgers_names() -> None:
    one = row(USD, EUR, "0.925", "2026-11-19", "online", "frankfurter")

    assert one.as_listed() == {
        "baseCurrencyAssetId": USD,
        "baseCurrencyCode": "USD",
        "quoteCurrencyAssetId": EUR,
        "quoteCurrencyCode": "EUR",
        "rate": "0.925",
        "rateDate": "2026-11-19",
        "source": "online",
        "onlineSourceId": "frankfurter",
    }
    assert one.where_from == "frankfurter"
    assert row(EUR, USD, "1.08", "2026-11-20").where_from == "typed in by hand"


def test_a_rate_long_ago_is_seven_days_or_more_before() -> None:
    def note(days: int | None) -> LedgerRateNote:
        return LedgerRateNote(outcome=LedgerRateOutcome.COMPARED, day=DAY, days_apart=days)

    assert LONG_AGO_DAYS == 7
    assert note(15).long_ago and note(7).long_ago
    assert not note(6).long_ago and not note(None).long_ago
