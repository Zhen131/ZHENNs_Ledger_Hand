"""Tests of what goes on a card: each cell kept, left empty, or left empty and doubted.

Each kind of cell said wrong in itself (the contract's table C) is left
empty and marked suspicious with what was said; three amounts that do not
agree leave the total empty; nothing empty is ever filled with 0. The
demo book's assets; "now" is 24 November 2026, 23:55 in Budapest. Every
figure is invented.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.card_record import (
    TAKEN_AS_TOTAL,
    CardRecord,
    Doubt,
    card_marks,
    card_record,
    money_doubt_other,
    money_doubt_two,
)
from ledger_hand.core.ledger_records import MarketPrice, MoneyAmount
from ledger_hand.core.ledger_table import table_of
from ledger_hand.core.marks import (
    FAR_REASON_START,
    REASON_MOST,
    Field,
    MarkKind,
    fields_sent,
    reason_length,
    sent_marks,
)
from ledger_hand.core.price_check import check_price
from ledger_hand.core.trade import (
    Amount,
    InferredFrom,
    OccurredTime,
    Side,
    TimePrecision,
    TradeDraft,
)
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.core.validation import DraftProblems, check_draft
from ledger_hand.ledger.demo_book import DEMO_ASSETS

ZONE = "Europe/Budapest"
_BUDAPEST = ZoneInfo(ZONE)
NOW = datetime(2026, 11, 24, 23, 55, tzinfo=_BUDAPEST)
TABLE = table_of(DEMO_ASSETS)
assert TABLE is not None
# More places after the point than the ledger holds.
TINY = Decimal("0." + "0" * 30 + "1")
TEN = OccurredTime(datetime(2026, 11, 24, 10, 0, tzinfo=_BUDAPEST), TimePrecision.MINUTE, ZONE)


def draft(**changes: object) -> TradeDraft:
    values: dict[str, object] = {
        "side": Side.BUY,
        "coin": "ETH",
        "quantity": Decimal("0.1"),
        "price": Decimal("2600"),
        "quote": "USDT",
        "fee": Decimal("0"),
        "occurred": TEN,
        "raw_text": "invented",
    }
    values.update(changes)
    return TradeDraft(**values)  # type: ignore[arg-type]


def made(one: TradeDraft, **options: object) -> CardRecord:
    problems = check_draft(one, TABLE, NOW)  # type: ignore[arg-type]
    assert isinstance(problems, DraftProblems), problems
    return card_record(one, problems, TABLE, NOW, **options)  # type: ignore[arg-type]


def doubt(card: CardRecord, field: Field) -> str:
    found = [mark for mark in card.doubts if mark.field is field]
    assert len(found) == 1, card.doubts
    reason = found[0].reason
    assert reason is not None and found[0].kind is MarkKind.SUSPICIOUS
    return reason


# --- table C: a cell said, but wrong in itself --------------------------------------------


@pytest.mark.parametrize(
    ("changes", "field", "words", "kind"),
    [
        ({"quantity": Decimal("0")}, Field.QUANTITY, "the quantity was 0", Doubt.NOT_ABOVE_ZERO),
        (
            {"quantity": TINY},
            Field.QUANTITY,
            f"the quantity was {TINY:f}",
            Doubt.TOO_MANY_DIGITS,
        ),
        ({"price": Decimal("-5")}, Field.PRICE, "the price was -5", Doubt.NOT_ABOVE_ZERO),
        (
            {"price": None, "total": Decimal("0")},
            Field.TOTAL_VALUE,
            "the total was 0",
            Doubt.NOT_ABOVE_ZERO,
        ),
        ({"fee": Decimal("-1")}, Field.FEE, "the fee was -1", Doubt.FEE_BELOW_ZERO),
        (
            {"fee": TINY, "fee_coin": "USDT"},
            Field.FEE,
            f"the fee was {TINY:f}",
            Doubt.TOO_MANY_DIGITS,
        ),
    ],
)
def test_a_figure_wrong_in_itself_is_left_empty_and_says_what_was_said(
    changes: dict[str, object], field: Field, words: str, kind: Doubt
) -> None:
    card = made(draft(**changes))

    assert field in card.empty
    reason = doubt(card, field)
    assert words in reason
    assert Doubt.of(reason) is kind


def test_a_fee_coin_that_cannot_be_a_code_leaves_the_fee_money_empty() -> None:
    card = made(draft(fee=Decimal("1"), fee_coin="手续费币"))

    assert card.fee == Decimal("1") and card.fee_coin is None
    assert Doubt.of(doubt(card, Field.FEE_ASSET_ID)) is Doubt.FEE_WORD_NOT_A_CODE
    assert '"手续费币"' in doubt(card, Field.FEE_ASSET_ID)


def test_a_time_with_seconds_in_its_offset_sends_the_day_alone_and_doubts_it() -> None:
    odd = timezone(timedelta(hours=1, seconds=20))
    moment = datetime(1890, 5, 1, 10, 0, tzinfo=odd)
    with pytest.raises(ValueError, match="offset"):
        OccurredTime(moment, TimePrecision.MINUTE, ZONE)
    lmt = OccurredTime(datetime(1890, 5, 1, 10, 0, tzinfo=_BUDAPEST), TimePrecision.MINUTE, ZONE)
    card = made(draft(occurred=lmt))

    assert card.occurred is not None and card.occurred.precision is TimePrecision.DAY
    assert card.occurred.value == date(1890, 5, 1)
    assert Doubt.of(doubt(card, Field.OCCURRED_DATE)) is Doubt.OFFSET_SECONDS


def test_a_day_after_today_is_left_empty_with_its_day() -> None:
    tomorrow = OccurredTime(date(2026, 11, 25), TimePrecision.DAY, ZONE)
    card = made(draft(occurred=tomorrow))

    assert card.occurred is None
    assert doubt(card, Field.OCCURRED_DATE) == "you said 2026-11-25, which is after today"


def test_a_note_too_long_is_not_sent_and_says_how_it_began() -> None:
    note = "很长的备注" * 1000
    card = made(draft(note=note))

    assert card.note is None
    reason = doubt(card, Field.NOTE)
    assert Doubt.of(reason) is Doubt.TOO_LONG and "很长的备注" in reason


# --- table B: cells not said ----------------------------------------------------------------


def test_cells_not_said_are_empty_never_0_and_carry_no_mark() -> None:
    card = made(draft(price=None, quote=None, fee=None, occurred=None))

    assert (card.price, card.total, card.quote, card.fee, card.fee_coin, card.occurred) == (
        None,
        None,
        None,
        None,
        None,
        None,
    )
    assert card.doubts == ()
    assert card.empty == {
        Field.OCCURRED_DATE,
        Field.PRICE,
        Field.TOTAL_VALUE,
        Field.QUOTE_ASSET_ID,
        Field.FEE,
        Field.FEE_ASSET_ID,
    }


def test_a_fee_of_0_with_no_money_said_has_no_money_either() -> None:
    card = made(draft(quote=None))

    assert card.fee == Decimal(0) and card.fee_coin is None


def test_two_figures_said_work_out_the_third() -> None:
    card = made(draft(quote=None))

    assert card.total == Decimal("260") and card.derived is Amount.TOTAL


# --- three figures that do not agree, and a fee not below the quantity ----------------------


def test_three_figures_that_disagree_are_all_kept_as_said() -> None:
    card = made(draft(quantity=Decimal("0.094326"), price=Decimal("212.03"), total=Decimal("200")))

    assert (card.quantity, card.price, card.total) == (
        Decimal("0.094326"),
        Decimal("212.03"),
        Decimal("200"),
    )
    reasons = {doubt(card, field) for field in (Field.QUANTITY, Field.PRICE, Field.TOTAL_VALUE)}
    (reason,) = reasons
    assert Doubt.of(reason) is Doubt.DISAGREE
    assert "200 USDT" in reason and "does not guess which is wrong" in reason


def test_a_fee_in_the_asset_bought_not_below_the_quantity_empties_the_fee() -> None:
    card = made(
        draft(coin="BTC", quantity=Decimal("0.001"), price=Decimal("60000"), fee=Decimal("0.002"),
              fee_coin="BTC")
    )  # fmt: skip

    assert card.quantity == Decimal("0.001") and card.fee is None
    assert doubt(card, Field.QUANTITY) == doubt(card, Field.FEE)
    assert Doubt.of(doubt(card, Field.FEE)) is Doubt.FEE_NOT_BELOW


def test_side_and_asset_are_never_left_empty() -> None:
    problems = check_draft(draft(side=None), TABLE, NOW)
    assert isinstance(problems, DraftProblems)
    with pytest.raises(ValueError, match="side and the asset"):
        card_record(draft(side=None), problems, TABLE, NOW)


# --- the marks of a card --------------------------------------------------------------------

SOL = MarketPrice(
    asset="SOL", price=MoneyAmount(currency="USDT", amount=Decimal("150")), day=date(2026, 11, 24)
)


def test_disagreeing_and_far_make_one_mark_with_the_disagreement_first() -> None:
    card = made(
        draft(coin="SOL", quantity=Decimal("0.094326"), price=Decimal("21.2"), total=Decimal("200"))
    )
    check = check_price(Decimal("21.2"), "USDT", [SOL], Decimal(5))

    marks = card_marks(card, check)
    price = marks.on(Field.PRICE)
    assert price is not None and price.reason is not None
    assert price.reason.index("does not guess") < price.reason.index(FAR_REASON_START)


def test_a_joined_reason_too_long_is_cut_from_the_far_half() -> None:
    long_note = "x" * 240
    card = made(
        draft(coin="SOL", quantity=Decimal("0.094326"), price=Decimal("21.2"), total=Decimal("200"))
    )
    card = CardRecord(
        **{
            **card.__dict__,
            "doubts": tuple(
                type(mark)(mark.field, mark.kind, long_note) if mark.field is Field.PRICE else mark
                for mark in card.doubts
            ),
        }
    )
    check = check_price(Decimal("21.2"), "USDT", [SOL], Decimal(5))

    price = card_marks(card, check).on(Field.PRICE)
    assert price is not None and price.reason is not None
    assert price.reason.startswith(long_note)
    assert reason_length(price.reason) <= REASON_MOST and price.reason.endswith("…")


def test_a_total_taken_from_25u_is_assumed_and_says_so() -> None:
    card = made(draft(quantity=None, price=None, total=Decimal("25")), taken_as_total="25U")

    total = card_marks(card, None).on(Field.TOTAL_VALUE)
    assert total is not None and total.kind is MarkKind.INFERRED
    assert total.reason == TAKEN_AS_TOTAL.format(said="25U")


def test_a_guess_sent_empty_keeps_no_assumed_mark() -> None:
    source = InferredFrom(
        trade_id="t-1", occurred=datetime(2026, 8, 3, tzinfo=_BUDAPEST), money="USDT", asset="ETH"
    )
    card = made(draft(fee=None))
    card = CardRecord(
        **{**card.__dict__, "fee_coin": None, "inferred": frozenset(), "inferred_from": source}
    )

    marks = card_marks(card, None)
    assert all(
        mark.kind is MarkKind.SUSPICIOUS for mark in marks.marks if mark.field in marks.empty
    )


def test_money_doubts_say_the_word_and_why() -> None:
    source = InferredFrom(
        trade_id="t-9", occurred=datetime(2026, 8, 9, tzinfo=_BUDAPEST), money="CNY", asset="ETH"
    )

    assert Doubt.of(money_doubt_two("刀", "ETH")) is Doubt.MONEY_TWO_USED
    other = money_doubt_other("刀", source)
    assert Doubt.of(other) is Doubt.MONEY_OTHER_USED
    assert "CNY" in other and "t-9" in other and "2026-08-09" in other


def test_every_doubt_has_a_start_of_its_own_and_far_is_none_of_them() -> None:
    assert Doubt.of(f"{FAR_REASON_START} of BTC") is None
    filled = {doubt: doubt.value.replace("{", "<").replace("}", ">") for doubt in Doubt}
    for doubt, reason in filled.items():
        assert Doubt.of(reason) is doubt, doubt


# --- what leaves for the ledger --------------------------------------------------------------


def test_an_empty_cell_is_sent_as_none_and_keeps_only_a_suspicious_mark() -> None:
    card = TradeCard(
        occurred=None,
        side=Side.BUY,
        asset="ETH",
        quantity=Decimal("0.1"),
        price=None,
        total=None,
        quote=None,
        fee=None,
        fee_asset=None,
        platform="",
        note="",
        raw_text="invented",
        zone=None,
        date_only=False,
    )
    record = made(draft(price=Decimal("0"), quote=None, fee=None, occurred=None))
    marks = card_marks(record, None)

    sent = sent_marks(marks, fields_sent(card))
    assert card.missing == (
        "occurredDate",
        "price",
        "totalValue",
        "quoteAssetId",
        "fee",
        "feeAssetId",
    )
    assert [(mark.field, mark.kind) for mark in sent] == [("price", "suspicious")]
    assert card.facts is None and not card.complete
