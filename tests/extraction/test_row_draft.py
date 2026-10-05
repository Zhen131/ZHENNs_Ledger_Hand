"""Tests of one row becoming a draft: how units, coins and the passage's own text are used.

Every passage and row below is invented.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.trade import Side
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.passage import Passage
from ledger_hand.extraction.reply_parser import ReplyRow
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.row_draft import RowDraft, Surroundings, draft_from_row
from tests.extraction.scripted_runs import NOW, ZONE


def made(passage: str, side: Side | None = Side.BUY, **cells: str) -> RowDraft:
    row = ReplyRow(side, {Field(name): text for name, text in cells.items()})
    return draft_from_row(row, 0, Surroundings(Passage(passage), BUILT_IN_TABLE, NOW, ZONE))


def kinds(result: RowDraft) -> list[IssueKind]:
    return [issue.kind for issue in result.issues]


# --- the unit on the price and the total -------------------------------------------


@pytest.mark.parametrize(
    ("passage", "price", "quote"),
    [
        ("6万刀买的 ETH", "6万刀", "刀"),
        ("price 3,420 USDT", "3,420 USDT", "USDT"),
        ("price $3,420", "$3,420", "$"),
        ("0.05 BTC 一个", "0.05 BTC", "BTC"),
        ("价格 3420u", "3420u", "u"),
    ],
)
def test_the_unit_of_the_price_fills_an_empty_pricing_currency(
    passage: str, price: str, quote: str
) -> None:
    result = made(passage, price=price)

    assert result.draft.quote == quote
    assert result.issues == ()


def test_the_unit_of_the_total_fills_an_empty_pricing_currency() -> None:
    result = made("花了 200U 买 DOGE", coin="DOGE", total="200U")

    assert result.draft.total == Decimal("200")
    assert result.draft.quote == "U"


def test_a_unit_that_agrees_with_the_pricing_currency_raises_nothing() -> None:
    result = made("3,420 USDT，用 U 算", price="3,420 USDT", price_currency="U")

    assert result.draft.quote == "U"
    assert result.issues == ()


def test_a_unit_that_names_another_pricing_currency_is_noted_and_the_field_kept() -> None:
    result = made("价格 0.05 BTC，按 USDT 记", price="0.05 BTC", price_currency="USDT")

    assert result.draft.quote == "USDT"
    assert result.draft.price == Decimal("0.05")
    assert result.issues == (
        Issue(
            kind=IssueKind.UNIT_NOT_THE_PRICE_CURRENCY,
            draft=0,
            field=Field.PRICE,
            phrase="BTC",
        ),
    )


def test_the_price_and_the_total_must_agree_on_their_currency() -> None:
    result = made("价格 6万刀，一共 0.5 BTC", price="6万刀", total="0.5 BTC")

    assert result.draft.quote == "刀"
    assert kinds(result) == [IssueKind.UNIT_NOT_THE_PRICE_CURRENCY]
    assert result.issues[0].field is Field.TOTAL


def test_a_unit_that_names_two_currencies_is_not_used() -> None:
    result = made("price 3 BTC USDT", price="3 BTC USDT")

    assert result.draft.price == Decimal("3")
    assert result.draft.quote is None
    assert kinds(result) == [IssueKind.UNIT_NAMES_SEVERAL]


def test_a_counter_on_the_price_names_no_currency() -> None:
    result = made("3,420 个", price="3,420 个")

    assert result.draft.quote is None
    assert result.issues == ()


# --- the unit on the fee ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("passage", "fee", "fee_coin"),
    [
        ("手续费 2 USDT", "2 USDT", "USDT"),
        ("fee 0.0005 BNB", "0.0005 BNB", "BNB"),
        ("手续费 1 刀", "1 刀", "刀"),
        ("fee 3 DOGE", "3 DOGE", "DOGE"),
    ],
)
def test_the_unit_of_the_fee_fills_an_empty_fee_currency(
    passage: str, fee: str, fee_coin: str
) -> None:
    result = made(passage, fee=fee)

    assert result.draft.fee_coin == fee_coin
    assert result.issues == ()


def test_a_fee_unit_that_names_another_currency_is_noted() -> None:
    result = made("fee 付的 BNB，0.1 USDT", fee="0.1 USDT", fee_currency="BNB")

    assert result.draft.fee_coin == "BNB"
    assert kinds(result) == [IssueKind.UNIT_NOT_THE_FEE_CURRENCY]


def test_a_fee_in_a_coin_outside_the_table_is_read_with_that_coin_as_its_unit() -> None:
    result = made("fee 付的 BONK 100 BONK", fee="100 BONK", fee_currency="BONK")

    assert result.draft.fee == Decimal("100")
    assert result.draft.fee_coin == "BONK"
    assert result.issues == ()


# --- the unit on the quantity -------------------------------------------------------------


@pytest.mark.parametrize(
    ("passage", "coin", "quantity"),
    [
        ("买了 0.02 个比特币", "比特币", "0.02 个比特币"),
        ("买了 0.02 BTC", "BTC", "0.02 BTC"),
        ("买了 0.02 BTC 大饼", "大饼", "0.02 BTC"),
        ("买了 200 个 ARB", "ARB", "200 个 ARB"),
        ("买了 500 BONK", "BONK", "500 BONK"),
        ("买了 3 枚 ETH", "ETH", "3 枚 ETH"),
        ("买了 3 个", "ETH", "3 个"),
    ],
)
def test_a_quantity_unit_that_is_the_trades_coin_raises_nothing(
    passage: str, coin: str, quantity: str
) -> None:
    passage = passage if coin in passage else passage + " " + coin

    result = made(passage, coin=coin, quantity=quantity)

    assert result.draft.quantity is not None
    assert result.issues == ()


@pytest.mark.parametrize(
    ("passage", "coin", "quantity"),
    [
        ("ETH 买了 0.5 BTC", "ETH", "0.5 BTC"),
        ("花 100U 买 ETH", "ETH", "100U"),
        ("买了 0.5 BTC", None, "0.5 BTC"),
    ],
)
def test_a_quantity_unit_that_is_not_the_trades_coin_is_noted_and_never_used(
    passage: str, coin: str | None, quantity: str
) -> None:
    cells = {"quantity": quantity} | ({"coin": coin} if coin else {})

    result = made(passage, **cells)

    assert kinds(result) == [IssueKind.UNIT_NOT_THE_COIN]
    assert result.draft.coin == (None if coin is None else BUILT_IN_TABLE.find(coin).symbol)  # type: ignore[union-attr]


# --- the coin ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("比特币", "BTC"),
        ("btc", "BTC"),
        ("姨太", "ETH"),
        ("ＥＴＨ", "ETH"),
        ("pepe2", "PEPE2"),
        ("Ｂｏｎｋ", "BONK"),
        ("邦克", "邦克"),
        ("USDT", "USDT"),
    ],
)
def test_the_coin_goes_in_by_its_symbol_or_as_a_capital_candidate(
    written: str, expected: str
) -> None:
    assert made(f"买了 {written}", coin=written).draft.coin == expected


# --- the passage's own text ---------------------------------------------------------------


def test_free_text_goes_in_as_the_passage_writes_it() -> None:
    passage = "在　ＯＫＸ 买的，觉得  还会涨"

    result = made(passage, platform="OKX", opinion="觉得 还会涨")

    assert result.draft.platform == "ＯＫＸ"
    assert result.draft.note == "觉得  还会涨"


def test_the_side_is_taken_as_chosen() -> None:
    assert made("x", side=Side.SELL).draft.side is Side.SELL
    assert made("x", side=None).draft.side is None


def test_the_numbers_a_rows_phrases_hold_are_handed_back() -> None:
    result = made("9:40 买 0.1 BTC 价格 6万", quantity="0.1 BTC", time="9:40", price="6万")

    assert sorted(result.numbers) == ["0.1", "40", "6万", "9"]


def test_a_phrase_not_in_the_passage_holds_no_numbers() -> None:
    assert made("买 0.1 BTC", quantity="0.2 BTC").numbers == ()
