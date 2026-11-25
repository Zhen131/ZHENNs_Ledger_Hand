"""Tests of the share set and of judging what came of one of its sentences.

The set loads, every gold answer is in shape, and the judging compares
every field by the ledger's code: a trade priced in USDT is never the gold
trade priced in USD. Every trade is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from evals.stock_set import (
    ASK,
    REFUSE,
    SEND,
    Outcome,
    StockGold,
    Verdict,
    judge,
    load_stock_set,
    passes,
)
from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.trade import Side

ZONE = ZoneInfo("Europe/Budapest")


def test_the_set_loads_and_covers_every_kind_of_sentence() -> None:
    stock_set = load_stock_set()

    assert len(stock_set.sentences) >= 12
    kinds = {sentence.kind for sentence in stock_set.sentences}
    assert {
        "told_in_full",
        "no_fee",
        "no_time_of_day",
        "no_money_said",
        "dao",
        "coin_and_share",
        "share_not_in_ledger",
        "open_order",
    } <= kinds
    texts = [sentence.text for sentence in stock_set.sentences]
    assert any(text.isascii() for text in texts)
    assert any(not text.isascii() for text in texts)


def first_gold() -> StockGold:
    (sentence, *_) = load_stock_set().sentences
    assert sentence.gold.expect == SEND
    return sentence.gold


def facts(**changed: object) -> TradeFacts:
    fields: dict[str, object] = {
        "occurred": datetime(2026, 11, 24, 15, 30, tzinfo=ZONE),
        "side": Side.BUY,
        "asset": "MSFT",
        "quantity": Decimal("2"),
        "price": Decimal("410"),
        "total": Decimal("820"),
        "quote": "USD",
        "fee": Decimal("1"),
        "fee_asset": "USD",
        "platform": "IBKR",
        "note": "",
        "raw_text": "invented",
    }
    fields.update(changed)
    return TradeFacts(**fields)  # type: ignore[arg-type]


def test_the_gold_trade_sent_is_right() -> None:
    assert judge(first_gold(), Outcome(sent=(facts(),))) is Verdict.RIGHT


def test_usdt_for_usd_is_silently_wrong() -> None:
    assert judge(first_gold(), Outcome(sent=(facts(quote="USDT"),))) is Verdict.SILENTLY_WRONG
    assert judge(first_gold(), Outcome(sent=(facts(fee_asset="USDT"),))) is Verdict.SILENTLY_WRONG


def test_a_figure_off_is_silently_wrong_and_nothing_sent_is_not_done() -> None:
    assert judge(first_gold(), Outcome(sent=(facts(total=Decimal("821")),))) is (
        Verdict.SILENTLY_WRONG
    )
    assert judge(first_gold(), Outcome(asked="fee")) is Verdict.NOT_DONE


def test_an_ask_is_right_only_for_its_cell_and_anything_sent_is_silently_wrong() -> None:
    gold = StockGold(expect=ASK, ask="pricing currency")

    assert judge(gold, Outcome(asked="pricing currency")) is Verdict.RIGHT
    assert judge(gold, Outcome(asked="fee")) is Verdict.NOT_DONE
    assert judge(gold, Outcome(sent=(facts(),))) is Verdict.SILENTLY_WRONG


def test_a_refusal_is_right_for_a_reason_it_allows() -> None:
    gold = StockGold(expect=REFUSE, why=frozenset({"not_in_ledger"}))

    assert judge(gold, Outcome(reasons=frozenset({"not_in_ledger"}))) is Verdict.RIGHT
    assert judge(gold, Outcome(reasons=frozenset({"no_trade"}))) is Verdict.NOT_DONE
    assert judge(gold, Outcome(sent=(facts(),))) is Verdict.SILENTLY_WRONG


def test_one_of_two_gold_trades_sent_is_not_done() -> None:
    (two,) = [s for s in load_stock_set().sentences if len(s.gold.trades) == 2]
    _, msft = two.gold.trades
    sent = facts(occurred=msft.occurred)

    assert judge(two.gold, Outcome(sent=(sent,))) is Verdict.NOT_DONE


def test_the_pass_lines() -> None:
    right = {f"K{n}": Verdict.RIGHT for n in range(1, 9)}

    assert passes({**right, "K9": Verdict.NOT_DONE, "K10": Verdict.NOT_DONE}) == {
        "nothing silently wrong": True,
        "at least 80% right": True,
    }
    assert not passes({**right, "K9": Verdict.SILENTLY_WRONG})["nothing silently wrong"]
