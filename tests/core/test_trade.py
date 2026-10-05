"""Tests of the shapes of a trade: the time it happened, a draft and a finished record."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.trade import (
    NOT_ZONE_NAMES,
    Amount,
    OccurredTime,
    Side,
    TimePrecision,
    TradeDraft,
    TradeRecord,
)

BUDAPEST = "Europe/Budapest"
BUDAPEST_ZONE = ZoneInfo(BUDAPEST)


def moment(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
    *,
    fold: int = 0,
) -> datetime:
    """A wall-clock time in Budapest."""
    return datetime(
        year, month, day, hour, minute, second, microsecond, tzinfo=BUDAPEST_ZONE, fold=fold
    )


# --- the names the ledger uses ----------------------------------------------


def test_enumerations_carry_the_words_the_ledger_writes() -> None:
    assert [side.value for side in Side] == ["buy", "sell"]
    assert [precision.value for precision in TimePrecision] == ["day", "minute", "second"]
    assert [amount.value for amount in Amount] == ["quantity", "price", "total"]


# --- when a trade happened --------------------------------------------------


def test_day_precision_holds_a_date() -> None:
    occurred = OccurredTime(date(2026, 10, 3), TimePrecision.DAY, BUDAPEST)

    assert occurred.value == date(2026, 10, 3)
    assert occurred.calendar_date == date(2026, 10, 3)
    assert occurred.time_zone == BUDAPEST


def test_minute_precision_holds_a_moment_with_its_zone() -> None:
    occurred = OccurredTime(moment(2026, 10, 4, 9, 40), TimePrecision.MINUTE, BUDAPEST)

    assert occurred.value == datetime(2026, 10, 4, 7, 40, tzinfo=timezone.utc)
    assert occurred.calendar_date == date(2026, 10, 4)


def test_second_precision_keeps_the_seconds() -> None:
    occurred = OccurredTime(moment(2026, 10, 4, 9, 40, 17), TimePrecision.SECOND, BUDAPEST)

    assert isinstance(occurred.value, datetime)
    assert occurred.value.second == 17


def test_calendar_date_is_the_date_on_the_wall_clock_not_the_utc_date() -> None:
    occurred = OccurredTime(moment(2026, 10, 4, 0, 30), TimePrecision.MINUTE, BUDAPEST)

    assert occurred.value.astimezone(timezone.utc).date() == date(2026, 10, 3)
    assert occurred.calendar_date == date(2026, 10, 4)


def test_moment_written_with_a_plain_offset_is_accepted_when_the_offset_is_the_zone_s() -> None:
    summer = timezone(timedelta(hours=2))

    occurred = OccurredTime(
        datetime(2026, 10, 4, 9, 40, tzinfo=summer), TimePrecision.MINUTE, BUDAPEST
    )

    assert occurred.value == moment(2026, 10, 4, 9, 40)


def test_both_readings_of_a_repeated_hour_are_accepted_and_differ() -> None:
    first = OccurredTime(moment(2026, 10, 25, 2, 30, fold=0), TimePrecision.MINUTE, BUDAPEST)
    second = OccurredTime(moment(2026, 10, 25, 2, 30, fold=1), TimePrecision.MINUTE, BUDAPEST)

    assert isinstance(first.value, datetime)
    assert isinstance(second.value, datetime)
    assert second.value - first.value == timedelta(hours=1)
    assert first.value < second.value
    assert first != second


def test_moment_is_kept_with_a_plain_fixed_offset() -> None:
    occurred = OccurredTime(moment(2026, 10, 4, 9, 40), TimePrecision.MINUTE, BUDAPEST)

    assert isinstance(occurred.value, datetime)
    assert isinstance(occurred.value.tzinfo, timezone)
    assert occurred.value.utcoffset() == timedelta(hours=2)
    assert occurred.value.isoformat() == "2026-10-04T09:40:00+02:00"


def test_same_moment_given_with_either_kind_of_zone_object_is_equal() -> None:
    summer = timezone(timedelta(hours=2))

    from_zone = OccurredTime(moment(2026, 10, 4, 9, 40), TimePrecision.MINUTE, BUDAPEST)
    from_offset = OccurredTime(
        datetime(2026, 10, 4, 9, 40, tzinfo=summer), TimePrecision.MINUTE, BUDAPEST
    )

    assert from_zone == from_offset


def test_day_precision_refuses_a_moment() -> None:
    with pytest.raises(ValueError, match="day"):
        OccurredTime(moment(2026, 10, 4, 9, 40), TimePrecision.DAY, BUDAPEST)


@pytest.mark.parametrize("precision", [TimePrecision.MINUTE, TimePrecision.SECOND])
def test_minute_and_second_precision_refuse_a_bare_date(precision: TimePrecision) -> None:
    with pytest.raises(ValueError, match="moment"):
        OccurredTime(date(2026, 10, 4), precision, BUDAPEST)


@pytest.mark.parametrize("precision", list(TimePrecision))
@pytest.mark.parametrize("value", ["2026-10-04", 20261004, None])
def test_value_that_is_neither_a_date_nor_a_moment_is_refused(
    value: object, precision: TimePrecision
) -> None:
    with pytest.raises(TypeError, match="date"):
        OccurredTime(value, precision, BUDAPEST)  # type: ignore[arg-type]


def test_moment_without_an_offset_is_refused() -> None:
    with pytest.raises(ValueError, match="offset"):
        OccurredTime(datetime(2026, 10, 4, 9, 40), TimePrecision.MINUTE, BUDAPEST)


@pytest.mark.parametrize("name", ["", "Mars/Olympus", "localtime", "+02:00", "Budapest time"])
def test_unknown_time_zone_name_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="time zone"):
        OccurredTime(date(2026, 10, 3), TimePrecision.DAY, name)


@pytest.mark.parametrize("name", ["Factory", "posixrules"])
def test_zone_database_files_that_are_no_zone_are_refused(name: str) -> None:
    # Python's zone database loads both; the ledger's runtime knows neither.
    for value, precision in (
        (date(2026, 10, 3), TimePrecision.DAY),
        (datetime(2026, 10, 3, 9, 40, tzinfo=timezone.utc), TimePrecision.MINUTE),
    ):
        with pytest.raises(ValueError, match=f"not a time zone name: '{name}'"):
            OccurredTime(value, precision, name)


def test_the_names_that_are_no_zone_are_exactly_these() -> None:
    assert frozenset({"localtime", "Factory", "posixrules"}) == NOT_ZONE_NAMES


def test_offset_that_disagrees_with_the_zone_is_refused() -> None:
    shanghai = timezone(timedelta(hours=8))

    with pytest.raises(ValueError, match="offset"):
        OccurredTime(datetime(2026, 10, 4, 9, 40, tzinfo=shanghai), TimePrecision.MINUTE, BUDAPEST)


def test_winter_offset_on_a_summer_day_is_refused() -> None:
    winter = timezone(timedelta(hours=1))

    with pytest.raises(ValueError, match="offset"):
        OccurredTime(datetime(2026, 7, 1, 9, 40, tzinfo=winter), TimePrecision.MINUTE, BUDAPEST)


def test_wall_time_skipped_when_the_clocks_go_forward_is_refused() -> None:
    with pytest.raises(ValueError, match="offset"):
        OccurredTime(moment(2026, 3, 29, 2, 30), TimePrecision.MINUTE, BUDAPEST)


def test_minute_precision_refuses_seconds() -> None:
    with pytest.raises(ValueError, match="finer"):
        OccurredTime(moment(2026, 10, 4, 9, 40, 17), TimePrecision.MINUTE, BUDAPEST)


@pytest.mark.parametrize("precision", [TimePrecision.MINUTE, TimePrecision.SECOND])
def test_fractions_of_a_second_are_refused(precision: TimePrecision) -> None:
    with pytest.raises(ValueError, match="finer"):
        OccurredTime(moment(2026, 10, 4, 9, 40, 0, 500), precision, BUDAPEST)


# --- whether a time lies in the future --------------------------------------

NOON = datetime(2026, 10, 4, 12, 0, tzinfo=BUDAPEST_ZONE)
NO_GRACE = timedelta(0)


@pytest.mark.parametrize(
    ("occurred_at", "grace", "in_the_future"),
    [
        (moment(2026, 10, 4, 11, 59), NO_GRACE, False),
        (moment(2026, 10, 4, 12, 0), NO_GRACE, False),
        (moment(2026, 10, 4, 12, 1), NO_GRACE, True),
        (moment(2026, 10, 4, 12, 1), timedelta(minutes=1), False),
        (moment(2026, 10, 4, 12, 2), timedelta(minutes=1), True),
    ],
)
def test_moment_is_in_the_future_when_it_is_more_than_the_grace_after_now(
    occurred_at: datetime, grace: timedelta, *, in_the_future: bool
) -> None:
    occurred = OccurredTime(occurred_at, TimePrecision.MINUTE, BUDAPEST)

    assert occurred.is_in_the_future(NOON, grace) is in_the_future


@pytest.mark.parametrize(
    ("day", "in_the_future"),
    [(date(2026, 10, 3), False), (date(2026, 10, 4), False), (date(2026, 10, 5), True)],
)
def test_day_is_in_the_future_when_it_is_after_today_whatever_the_grace(
    day: date, *, in_the_future: bool
) -> None:
    occurred = OccurredTime(day, TimePrecision.DAY, BUDAPEST)

    assert occurred.is_in_the_future(NOON, NO_GRACE) is in_the_future
    assert occurred.is_in_the_future(NOON, timedelta(days=3)) is in_the_future


def test_today_is_read_in_the_zone_of_the_time_itself() -> None:
    late_evening = datetime(2026, 10, 4, 23, 30, tzinfo=BUDAPEST_ZONE)
    fifth = date(2026, 10, 5)

    in_budapest = OccurredTime(fifth, TimePrecision.DAY, BUDAPEST)
    in_shanghai = OccurredTime(fifth, TimePrecision.DAY, "Asia/Shanghai")

    assert in_budapest.is_in_the_future(late_evening, NO_GRACE)
    assert not in_shanghai.is_in_the_future(late_evening, NO_GRACE)


def test_future_test_refuses_a_now_without_an_offset() -> None:
    occurred = OccurredTime(date(2026, 10, 3), TimePrecision.DAY, BUDAPEST)

    with pytest.raises(ValueError, match="offset"):
        occurred.is_in_the_future(datetime(2026, 10, 4, 12, 0), NO_GRACE)


def test_occurred_time_cannot_be_changed() -> None:
    occurred = OccurredTime(date(2026, 10, 3), TimePrecision.DAY, BUDAPEST)

    with pytest.raises(dataclasses.FrozenInstanceError):
        occurred.time_zone = "UTC"  # type: ignore[misc]


# --- a draft ----------------------------------------------------------------


def test_every_field_of_a_draft_may_be_blank() -> None:
    draft = TradeDraft()

    blank = [field.name for field in dataclasses.fields(draft) if field.name != "derived"]
    assert [getattr(draft, name) for name in blank] == [None] * len(blank)
    assert draft.derived == frozenset()


def test_draft_fields_are_the_ones_later_steps_rely_on() -> None:
    assert [field.name for field in dataclasses.fields(TradeDraft)] == [
        "side",
        "coin",
        "quantity",
        "price",
        "total",
        "quote",
        "fee",
        "fee_coin",
        "occurred",
        "platform",
        "note",
        "raw_text",
        "derived",
    ]


def test_draft_is_filled_by_keyword_only() -> None:
    with pytest.raises(TypeError):
        TradeDraft(Side.BUY)  # type: ignore[misc]


def test_draft_cannot_be_changed_but_can_be_copied_with_new_values() -> None:
    draft = TradeDraft(coin="BTC")

    with pytest.raises(dataclasses.FrozenInstanceError):
        draft.coin = "ETH"  # type: ignore[misc]
    assert dataclasses.replace(draft, fee=Decimal(0)) == TradeDraft(coin="BTC", fee=Decimal(0))


def test_stated_amount_is_what_was_said() -> None:
    draft = TradeDraft(quantity=Decimal("0.02"), price=Decimal("94900"))

    assert draft.stated(Amount.QUANTITY) == Decimal("0.02")
    assert draft.stated(Amount.PRICE) == Decimal("94900")
    assert draft.stated(Amount.TOTAL) is None


def test_amount_marked_as_derived_does_not_count_as_stated() -> None:
    draft = TradeDraft(
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        total=Decimal("1898"),
        derived=frozenset({Amount.TOTAL}),
    )

    assert draft.total == Decimal("1898")
    assert draft.stated(Amount.TOTAL) is None
    assert draft.stated(Amount.QUANTITY) == Decimal("0.02")


@pytest.mark.parametrize("field", ["quantity", "price", "total", "fee"])
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_draft_refuses_a_number_that_is_not_finite(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        TradeDraft(**{field: Decimal(value)})  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["quantity", "price", "total", "fee"])
@pytest.mark.parametrize("value", [0.02, 1, "0.02"])
def test_draft_refuses_a_number_that_is_not_an_exact_decimal(field: str, value: object) -> None:
    with pytest.raises(TypeError, match=field):
        TradeDraft(**{field: value})  # type: ignore[arg-type]


# --- a finished record ------------------------------------------------------


def record() -> TradeRecord:
    return TradeRecord(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        total=Decimal("1898"),
        derived=Amount.TOTAL,
        fee=Decimal("2"),
        fee_coin="USDT",
        occurred=OccurredTime(moment(2026, 10, 4, 9, 40), TimePrecision.MINUTE, BUDAPEST),
        raw_text="9:40 bought 0.02 BTC at 94900, fee 2 USDT",
    )


def test_record_keeps_what_it_was_built_with() -> None:
    built = record()

    assert built.side is Side.BUY
    assert built.derived is Amount.TOTAL
    assert built.platform is None
    assert built.note is None


def test_record_cannot_be_changed() -> None:
    built = record()

    with pytest.raises(dataclasses.FrozenInstanceError):
        built.price = Decimal("1")  # type: ignore[misc]


def test_record_is_filled_by_keyword_only() -> None:
    with pytest.raises(TypeError):
        TradeRecord(Side.BUY, "BTC")  # type: ignore[call-arg,misc]
