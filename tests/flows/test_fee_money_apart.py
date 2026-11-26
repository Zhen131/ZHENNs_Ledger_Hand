"""Tests of the mark on a fee taken in one money while the trade is recorded as paid in another.

"今天15:30花了128欧元买了2股KO，合139美元，……换汇费0.19欧元": when the model
copies the dollars as the total, the trade goes as paid in USD while its
fee is in EUR. Nothing is changed or asked for it: the fee's money is
marked suspicious, and the reply says so (decided on 2026-11-26, on the
review of the euro part). A fee taken in the asset traded, or a fee or
trade whose money is empty, is not marked; a trade paid in euros with an
FX fee in euros is not either. Every sentence and number is invented; the
ledgers are made in ``paid_apart_books``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.marks import (
    Field,
    FieldMark,
    MarkKind,
    TradeMarks,
    fee_money_mark,
    with_mark,
)
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.conversation import Said
from tests.flows import paid_apart_books as books
from tests.flows.test_paid_apart_examples import E1, E1_ROW, KO, one, sent

FEE_MARK = (
    "feeAssetId is marked suspicious: the fee is in EUR, but this trade is recorded as paid in USD"
)
DOLLARS_COPIED = KO | {"price": "69.5美元", "total": "139美元", "fee": "0.19欧元"}


def _fee_mark(card: TradeCard) -> tuple[str, str]:
    (mark,) = [mark for mark in card.marks if mark.field == "feeAssetId"]
    return mark.kind, mark.reason or ""


def _only_marked(said: Said) -> TradeCard:
    (card,) = sent(said)
    assert (card.quote, card.fee_asset, card.fee) == ("USD", "EUR", Decimal("0.19"))
    assert (card.price, card.total, card.cost_rate) == (Decimal("69.5"), Decimal(139), None)
    kind, reason = _fee_mark(card)
    assert kind == MarkKind.SUSPICIOUS.value
    assert reason == (
        "the fee is in EUR, but this trade is recorded as paid in USD; "
        "check which money you paid in"
    )
    assert FEE_MARK in said.reply
    return card


@pytest.mark.parametrize(
    ("said", "cells"),
    [
        ("今天15:30花了128欧元买了2股KO，合139美元，一股69.5美元，换汇费0.19欧元", DOLLARS_COPIED),
        (
            "今天15:30买了2股KO，一股69.5美元，一共139美元，实际付了128欧元，换汇费0.19欧元",
            DOLLARS_COPIED,
        ),
        (
            "今天15:30花了128欧元（约139美元）买了2股KO，一股69.5美元，换汇费0.19欧元",
            KO | {"price": "69.5美元", "fee": "0.19欧元"},
        ),
    ],
    ids=["dollars-after-euros", "euros-said-last", "dollars-in-brackets"],
)
def test_the_three_ways_of_saying_both_totals_mark_the_fees_money_and_change_nothing(
    said: str, cells: dict[str, str]
) -> None:
    card = _only_marked(one(said, cells, books.jia()))

    others = {mark.field for mark in card.marks} - {"feeAssetId"}
    assert others <= {"totalValue"}  # the total worked out, where the dollars were not copied


def test_a_fee_in_usdt_on_a_trade_paid_in_dollars_is_marked() -> None:
    said = one(
        "今天15:30买了2股KO，一股69.5美元，手续费0.5 USDT",
        KO | {"price": "69.5美元", "fee": "0.5 USDT"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.fee_asset) == ("USD", "USDT")
    assert _fee_mark(card)[0] == MarkKind.SUSPICIOUS.value
    assert "the fee is in USDT, but this trade is recorded as paid in USD" in said.reply


def test_a_fee_taken_in_the_coin_bought_is_not_marked() -> None:
    said = one(
        "今天上午10点买了0.01个BTC，价格98000 USDT，手续费0.00001 BTC",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "0.01个BTC",
            "price": "98000 USDT",
            "fee": "0.00001 BTC",
            "time": "今天上午10点",
        },
        books.jia(),
    )

    (card,) = sent(said)
    assert card.fee_asset == "BTC"
    assert all(mark.field != "feeAssetId" for mark in card.marks)


def test_a_fee_whose_money_is_empty_is_not_marked() -> None:
    said = one(
        "今天15:30买了2股KO，一股69.5美元",
        KO | {"price": "69.5美元"},
        books.jia(),
    )

    (card,) = sent(said)
    assert card.fee_asset is None
    assert all(mark.field != "feeAssetId" for mark in card.marks)


def test_a_trade_paid_in_euros_with_its_fx_fee_in_euros_is_not_marked_more() -> None:
    said = one(E1, E1_ROW, books.jia())

    (card,) = sent(said)
    assert (card.quote, card.fee_asset) == ("EUR", "EUR")
    assert all(mark.field != "feeAssetId" for mark in card.marks)
    assert "feeAssetId is marked suspicious" not in said.reply


def test_an_assumed_fee_money_marked_too_keeps_one_suspicious_mark_with_both_reasons() -> None:
    assumed = FieldMark(Field.FEE_ASSET_ID, MarkKind.INFERRED, "assumed from the last KO trade")

    marks = with_mark(TradeMarks(marks=(assumed,)), fee_money_mark("EUR", "USD"))

    (mark,) = marks.marks
    assert mark.kind is MarkKind.SUSPICIOUS
    assert mark.reason == (
        "assumed from the last KO trade; the fee is in EUR, but this trade is recorded as paid "
        "in USD; check which money you paid in"
    )
