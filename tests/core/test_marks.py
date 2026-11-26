"""Tests of the marks on a trade's cells: the ledger's rules, cutting a reason, and the guard.

A reason is counted as the ledger counts it, in UTF-16 units: an emoji
or a character of the extended range (𠀀) counts two. Every figure and
sentence is invented.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.ledger_records import MarketPrice, MoneyAmount
from ledger_hand.core.marks import (
    FAR_REASON_START,
    REASON_MOST,
    Field,
    FieldMark,
    MarkKind,
    TradeMarks,
    as_sent,
    cut_reason,
    marks_for,
    reason_length,
)
from ledger_hand.core.price_check import check_price
from ledger_hand.core.trade import (
    Amount,
    Inferred,
    InferredFrom,
    OccurredTime,
    Side,
    TimePrecision,
    TradeRecord,
)

_BUDAPEST = ZoneInfo("Europe/Budapest")
BTC = MarketPrice(
    asset="BTC", price=MoneyAmount(currency="USDT", amount=Decimal("64880")), day=date(2026, 11, 24)
)


def record(**changes: object) -> TradeRecord:
    values: dict[str, object] = {
        "side": Side.BUY,
        "coin": "BTC",
        "quantity": Decimal("0.01"),
        "price": Decimal("950"),
        "total": Decimal("9.50"),
        "quote": "USDT",
        "derived": Amount.TOTAL,
        "fee": Decimal("0"),
        "fee_coin": "USDT",
        "occurred": OccurredTime(
            datetime(2026, 11, 24, 11, 0, tzinfo=_BUDAPEST),
            TimePrecision.MINUTE,
            "Europe/Budapest",
        ),
        "raw_text": "invented",
    }
    values.update(changes)
    return TradeRecord(**values)  # type: ignore[arg-type]


# --- the ledger's four rules -----------------------------------------------------------


def test_one_cell_carries_one_mark_at_most() -> None:
    with pytest.raises(ValueError):
        TradeMarks(
            marks=(
                FieldMark(Field.PRICE, MarkKind.COMPUTED),
                FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, "far"),
            )
        )


@pytest.mark.parametrize("reason", [None, "   "])
def test_a_suspicious_mark_says_why(reason: str | None) -> None:
    with pytest.raises(ValueError):
        FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, reason)


def test_a_reason_of_256_units_is_taken_and_one_of_257_refused() -> None:
    FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, "a" * 256)

    with pytest.raises(ValueError):
        FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, "a" * 257)
    with pytest.raises(ValueError):
        FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, "a" * 255 + "😀")


def test_an_empty_cell_can_only_be_suspicious() -> None:
    TradeMarks(
        marks=(FieldMark(Field.FEE, MarkKind.SUSPICIOUS, "said -1"),), empty=frozenset({Field.FEE})
    )

    for kind in (MarkKind.COMPUTED, MarkKind.INFERRED):
        with pytest.raises(ValueError):
            TradeMarks(marks=(FieldMark(Field.FEE, kind),), empty=frozenset({Field.FEE}))


def test_the_names_are_the_ledgers_own() -> None:
    assert [kind.value for kind in MarkKind] == ["computed", "inferred", "suspicious"]
    assert [field.value for field in Field] == [
        "occurredDate",
        "occurredTime",
        "occurredTimeZone",
        "type",
        "assetId",
        "quantity",
        "price",
        "totalValue",
        "quoteAssetId",
        "fee",
        "feeAssetId",
        "costRate",
        "platform",
        "note",
    ]


# --- cutting a reason ------------------------------------------------------------------


def test_an_emoji_256_long_in_python_but_257_in_utf16_is_cut() -> None:
    reason = "a" * 255 + "😀"
    assert len(reason) == 256 and reason_length(reason) == 257

    cut = cut_reason(reason)

    assert reason_length(cut) <= REASON_MOST
    assert cut == "a" * 255 + "…"


def test_a_long_reason_of_extended_characters_is_cut_without_splitting_one() -> None:
    reason = "𠀀" * 200

    cut = cut_reason(reason)

    assert cut.endswith("…")
    assert reason_length(cut) <= REASON_MOST
    assert set(cut[:-1]) == {"𠀀"}
    cut.encode("utf-16-le")  # no half of a character is left behind


def test_a_reason_of_exactly_256_units_is_not_cut() -> None:
    reason = "b" * 254 + "😀"
    assert reason_length(reason) == 256

    assert cut_reason(reason) == reason


# --- working the marks out -----------------------------------------------------------


def test_the_total_worked_out_and_a_price_far_off_are_marked() -> None:
    check = check_price(Decimal("950"), "USDT", [BTC], Decimal(5))

    marks = marks_for(record(), check)

    assert [(mark.field, mark.kind) for mark in marks.marks] == [
        (Field.PRICE, MarkKind.SUSPICIOUS),
        (Field.TOTAL_VALUE, MarkKind.COMPUTED),
    ]
    reason = marks.on(Field.PRICE)
    assert reason is not None and reason.reason is not None
    assert reason.reason.startswith(FAR_REASON_START)


def test_a_price_worked_out_and_far_keeps_suspicious_with_the_other_reason_first() -> None:
    check = check_price(Decimal("95"), "USDT", [BTC], Decimal(5))

    marks = marks_for(
        record(
            price=Decimal("95"), total=Decimal("950"), quantity=Decimal("10"), derived=Amount.PRICE
        ),
        check,
    )

    (mark,) = marks.marks
    assert mark.kind is MarkKind.SUSPICIOUS
    assert mark.reason is not None
    assert mark.reason.startswith("worked out as total ÷ quantity; " + FAR_REASON_START)


def test_two_reasons_too_long_together_are_cut_the_dropped_one_first() -> None:
    long_asset = "X" * 170
    market = MarketPrice(asset=long_asset, price=MoneyAmount(currency="USDT", amount=Decimal(100)))
    check = check_price(Decimal("1"), "USDT", [market], Decimal(5))

    marks = marks_for(
        record(
            coin=long_asset,
            price=Decimal("1"),
            total=Decimal("10"),
            quantity=Decimal("10"),
            derived=Amount.PRICE,
        ),
        check,
    )

    (mark,) = marks.marks
    assert mark.reason is not None
    assert reason_length(mark.reason) <= REASON_MOST
    dropped, _, own = mark.reason.partition("; ")
    assert own.startswith(FAR_REASON_START)
    assert dropped.endswith("…") and dropped.startswith("worked")


def test_moneys_guessed_and_an_asset_matched_are_assumed() -> None:
    source = InferredFrom(
        trade_id="t-11",
        occurred=datetime(2026, 11, 19, 10, 5, tzinfo=_BUDAPEST),
        money="USDT",
        asset="ETH",
    )
    guessed = record(
        coin="ETH",
        inferred=frozenset({Inferred.QUOTE, Inferred.FEE_COIN}),
        inferred_from=source,
        picked="以太坊",
    )

    marks = marks_for(guessed, None, asset_name="Ethereum")

    found = {mark.field: mark for mark in marks.marks}
    assert found[Field.QUOTE_ASSET_ID].kind is MarkKind.INFERRED
    assert found[Field.FEE_ASSET_ID].kind is MarkKind.INFERRED
    assert "t-11, 2026-11-19" in (found[Field.QUOTE_ASSET_ID].reason or "")
    assert found[Field.ASSET_ID].kind is MarkKind.INFERRED
    assert '"以太坊" was matched to ETH (Ethereum)' in (found[Field.ASSET_ID].reason or "")


def test_nothing_said_by_the_user_is_marked() -> None:
    assert marks_for(record(derived=None), None).marks == ()


# --- the guard before marks are sent --------------------------------------------------


def test_a_cell_not_sent_keeps_only_a_suspicious_mark_and_the_time_none() -> None:
    marks = TradeMarks(
        marks=(
            FieldMark(Field.OCCURRED_TIME, MarkKind.SUSPICIOUS, "odd"),
            FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, "said 0"),
            FieldMark(Field.TOTAL_VALUE, MarkKind.COMPUTED, "worked out"),
            FieldMark(Field.FEE_ASSET_ID, MarkKind.INFERRED, "assumed"),
            FieldMark(Field.QUANTITY, MarkKind.COMPUTED, "worked out"),
        )
    )

    wire = as_sent(marks, frozenset({Field.QUANTITY}))

    assert wire == (
        {"field": "price", "kind": "suspicious", "reason": "said 0"},
        {"field": "quantity", "kind": "computed", "reason": "worked out"},
    )
    assert all(set(mark) == {"field", "kind", "reason"} for mark in wire)
