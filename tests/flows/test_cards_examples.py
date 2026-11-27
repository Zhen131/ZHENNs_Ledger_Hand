"""Tests of the assistant sending a card with cells left empty, one for each row of the table.

Once the ledger takes a trade with cells left empty, the assistant asks
only which asset and buy or sell (and a vague word for money the ledger
cannot settle); every other gap becomes a card: the cell empty, never 0,
and a cell said wrong left empty with a suspicious mark that says what
was said. The demo book, taking cards, unless a row makes its own
ledger; "now" is its fixed moment (24 November 2026, 23:55 in Budapest);
five times apart is far. A scripted model stands in for every call, and
its table of what it read is written out in each test. Every sentence
and number is invented.
"""

from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.card_record import Doubt
from ledger_hand.core.ledger_records import AssetKind, Pricing, TradeFilter
from ledger_hand.core.marks import (
    REASON_MOST,
    Field,
    FieldMark,
    MarkKind,
    TradeMarks,
    reason_length,
)
from ledger_hand.core.price_check import PriceVerdict
from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.assistant_record import entry_for
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.record_words import price_check_words
from ledger_hand.flows.recorded import MarkedTrade, RecordEnding
from ledger_hand.flows.standing import DemoOutcome, demo_save
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.flows.scripted_flow import copied, row, screened, table
from tests.flows.vague_money_books import JIA_ASSETS, JIA_TRADES, FailingTrades, asset, bought

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
EMPTY = "with empty fields"
NOT_GUESSED = "does not guess which is wrong"
FAR = "far from the market price"
NOT_COMPARED = "not compared with the market price"
_BUDAPEST = ZoneInfo(INVENTED_ZONE)


def cards() -> FakeLedger:
    """The demo ledger, taking cards with cells left empty, as the real ledger does now."""
    return demo_ledger().taking_cards()


def talk(
    *said: str,
    rows: list[dict[str, str]],
    ledger: FakeLedger | None = None,
    answers: tuple[Step, ...] = (),
) -> tuple[list[Said], FakeLedger]:
    """What comes of saying each of ``said`` in one chat, the model reading ``rows``."""
    ledger = ledger if ledger is not None else cards()
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said[0][:6]))],
        extraction=[table(*rows)],
        answers=answers,
    )
    state = AssistantChat()
    seen: list[Said] = []
    for words in said:
        result = say(
            state,
            words,
            model=model,
            ledger=ledger,
            now=INVENTED_NOW,
            zone=INVENTED_ZONE,
            max_steps=6,
        )
        seen.append(result)
        state = result.state
    return seen, ledger


def one(words: str, cells: dict[str, str], ledger: FakeLedger | None = None) -> Said:
    (said,), _ = talk(words, rows=[row(**cells)], ledger=ledger)
    return said


def card(said: Said) -> tuple[TradeCard, MarkedTrade]:
    """The one card sent, and its marks; it waits in the ledger."""
    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT, said.reply
    (sent,) = recorded.trades
    (marked,) = recorded.marked
    return sent, marked


def kinds(marks: TradeMarks) -> dict[Field, MarkKind]:
    return {mark.field: mark.kind for mark in marks.marks}


def mark_on(marks: TradeMarks, field: Field) -> FieldMark:
    found = marks.on(field)
    assert found is not None, marks
    return found


def wire(sent: TradeCard) -> dict[str, tuple[str, str | None]]:
    """The marks a card was sent with, by cell."""
    return {mark.field: (mark.kind, mark.reason) for mark in sent.marks}


def asked(said: Said, ledger: FakeLedger, label: str) -> None:
    """A question waits, about ``label``; nothing was sent."""
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING, said.reply
    assert label in said.reply, said.reply
    assert said.sent is None
    assert "propose_add" not in ledger.calls


ETH = {"side": "buy", "coin": "ETH", "quantity": "0.1个ETH", "time": "今天上午10点"}


# --- row 1: the fourth sentence, whole --------------------------------------------------------


def test_row_01_the_950_card_is_whole_and_its_marks_reach_the_ledger() -> None:
    said = one(
        "今天上午11点在币安0.01个BTC 花了950U，手续费0",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "0.01个BTC",
            "price": "950U",
            "fee": "0",
            "time": "今天上午11点",
            "platform": "币安",
        },
    )

    sent, marked = card(said)
    assert sent.complete
    assert kinds(marked.marks) == {
        Field.PRICE: MarkKind.SUSPICIOUS,
        Field.TOTAL_VALUE: MarkKind.COMPUTED,
    }
    assert wire(sent)["price"][0] == "suspicious"
    assert wire(sent)["totalValue"][0] == "computed"
    assert said.recorded is not None
    (check,) = said.recorded.checks
    assert check.ready is True and check.missing == ()
    assert FAR in said.reply and EMPTY not in said.reply


def test_row_01_the_ledger_keeps_the_marks_as_they_came() -> None:
    (said,), ledger = talk(
        "今天上午11点在币安0.01个BTC 花了950U，手续费0",
        rows=[
            row(
                side="buy",
                coin="BTC",
                quantity="0.01个BTC",
                price="950U",
                fee="0",
                time="今天上午11点",
            )
        ],
    )

    assert said.sent is not None
    kept = ledger.marks_of(said.sent.proposals[0])
    assert {(mark.field, mark.kind) for mark in kept} == {
        ("price", "suspicious"),
        ("totalValue", "computed"),
    }


# --- rows 2 to 8: cells not said -------------------------------------------------------------


def test_row_02_no_fee_said_is_a_card_with_the_fee_and_its_money_empty() -> None:
    said = one("今天上午10点买了0.1个ETH，价格2600 USDT", ETH | {"price": "2600 USDT"})

    sent, marked = card(said)
    assert sent.fee is None and sent.fee_asset is None
    assert sent.missing == ("fee", "feeAssetId")
    assert Field.FEE in marked.marks.empty and Field.FEE_ASSET_ID in marked.marks.empty
    assert said.recorded is not None
    (check,) = said.recorded.checks
    assert check.ready is False and check.missing == ("fee", "feeAssetId")
    assert "Trade 1 was sent with empty fields: fee, feeAssetId." in said.reply
    assert "fee" not in [mark.field for mark in sent.marks]


def test_row_03_a_fee_with_no_money_said_leaves_only_its_money_empty() -> None:
    said = one(
        "今天上午10点买了0.1个ETH，价格2600 USDT，手续费0.5",
        ETH | {"price": "2600 USDT", "fee": "0.5"},
    )

    sent, _ = card(said)
    assert sent.fee == Decimal("0.5")
    assert sent.missing == ("feeAssetId",)
    assert EMPTY in said.reply


def test_row_04_no_time_at_all_sends_no_day_no_time_and_no_zone() -> None:
    cells = {
        "side": "buy",
        "coin": "ETH",
        "quantity": "0.1个ETH",
        "price": "2600 USDT",
        "fee": "0",
    }
    said = one("买了0.1个ETH，价格2600 USDT，手续费0", cells)

    sent, marked = card(said)
    assert sent.occurred is None and sent.zone is None and not sent.date_only
    assert sent.missing == ("occurredDate",)
    assert not {"occurredTime", "occurredTimeZone"} & set(wire(sent))
    assert Field.OCCURRED_DATE in marked.marks.empty
    assert EMPTY in said.reply


def test_row_05_a_day_alone_is_whole_and_sends_the_day() -> None:
    said = one(
        "11月20号买了0.1个ETH，价格2600 USDT，手续费0",
        ETH | {"time": "11月20号", "price": "2600 USDT", "fee": "0"},
    )

    sent, _ = card(said)
    assert sent.complete and sent.date_only
    assert sent.day == date(2026, 11, 20)
    assert EMPTY not in said.reply


def test_row_06_25u_said_as_the_quantity_is_taken_as_the_total_and_assumed() -> None:
    said = one(
        "今天上午10点用25U买了点ETH，手续费0",
        {"side": "buy", "coin": "ETH", "quantity": "25U", "fee": "0", "time": "今天上午10点"},
    )

    sent, marked = card(said)
    assert (sent.quantity, sent.price, sent.total, sent.quote) == (None, None, Decimal(25), "USDT")
    total = mark_on(marked.marks, Field.TOTAL_VALUE)
    assert total.kind is MarkKind.INFERRED
    assert total.reason is not None and "25U" in total.reason
    assert sent.missing == ("quantity", "price")
    assert EMPTY in said.reply
    assert said.recorded is not None and said.recorded.left_out == ()


def test_row_06b_25_read_as_the_total_is_sent_unmarked() -> None:
    said = one(
        "今天上午10点用25 USDT买了点ETH，手续费0",
        {"side": "buy", "coin": "ETH", "total": "25 USDT", "fee": "0", "time": "今天上午10点"},
    )

    sent, marked = card(said)
    assert (sent.quantity, sent.price, sent.total) == (None, None, Decimal(25))
    assert marked.marks.on(Field.TOTAL_VALUE) is None
    assert EMPTY in said.reply


def test_row_07_no_price_and_no_total_leaves_both_empty() -> None:
    said = one("今天上午10点买了0.1个ETH，手续费0", ETH | {"fee": "0"})

    sent, marked = card(said)
    assert (sent.price, sent.total) == (None, None)
    # No word for money was said either, so the money used is empty too.
    assert sent.missing == ("price", "totalValue", "quoteAssetId", "feeAssetId")
    assert marked.price.verdict is PriceVerdict.NO_PRICE
    assert EMPTY in said.reply


def test_row_08_no_quantity_leaves_it_and_the_total_empty() -> None:
    cells = {"side": "buy", "coin": "ETH", "price": "2600 USDT", "fee": "0", "time": "今天上午10点"}
    said = one("今天上午10点买了ETH，价格2600 USDT，手续费0", cells)

    sent, _ = card(said)
    assert (sent.quantity, sent.total, sent.price) == (None, None, Decimal(2600))
    assert EMPTY in said.reply


# --- row 9: three figures that do not agree -------------------------------------------------


SOL_200 = {
    "side": "buy",
    "coin": "SOL",
    "quantity": "0.094326个SOL",
    "price": "212.03 USDT",
    "total": "200 USDT",
    "fee": "0",
    "time": "今天上午8:25",
}


def test_row_09_three_figures_that_disagree_are_sent_as_said_all_three_suspicious() -> None:
    said = one("今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT，手续费0", SOL_200)

    sent, marked = card(said)
    assert (sent.quantity, sent.price, sent.total) == (
        Decimal("0.094326"),
        Decimal("212.03"),
        Decimal("200"),
    )
    for field in (Field.QUANTITY, Field.PRICE, Field.TOTAL_VALUE):
        assert mark_on(marked.marks, field).kind is MarkKind.SUSPICIOUS
    total = mark_on(marked.marks, Field.TOTAL_VALUE)
    assert total.reason is not None and "200 USDT" in total.reason
    assert Doubt.of(total.reason) is Doubt.DISAGREE
    assert NOT_GUESSED in said.reply
    assert "0.094326" in said.reply and "212.03" in said.reply and "200" in said.reply
    assert "which-cell" not in said.reply and "Which" not in said.reply


# --- rows 10 to 13 and 15c: what is still asked -----------------------------------------------


def test_row_10_an_asset_not_said_is_asked() -> None:
    (said,), ledger = talk(
        "今天买了点那个币，花了30 USDT",
        rows=[row(side="buy", total="30 USDT", time="今天")],
    )

    asked(said, ledger, "asset")


def test_row_11_buy_or_sell_not_said_is_asked() -> None:
    (said,), ledger = talk(
        "今天上午10点0.1个ETH，价格2600 USDT，手续费0",
        rows=[
            row(coin="ETH", quantity="0.1个ETH", price="2600 USDT", fee="0", time="今天上午10点")
        ],
    )

    asked(said, ledger, "buy")


DOT_30 = {
    "side": "buy",
    "coin": "DOT",
    "total": "30美金",
    "price": "5",
    "fee": "0",
    "time": "今天上午10点",
}


def test_row_12_a_vague_money_for_an_asset_with_no_trade_is_asked() -> None:
    (said,), ledger = talk("今天上午10点花了30美金买了DOT，均价5，手续费0", rows=[row(**DOT_30)])

    asked(said, ledger, "pricing currency")


def test_row_13_answered_us_dollars_it_is_sent_in_usd_with_no_guess() -> None:
    (first, second), ledger = talk(
        "今天上午10点花了30美金买了DOT，均价5，手续费0",
        "美元",
        rows=[row(**DOT_30)],
        answers=(copied("美元"),),
    )

    assert first.sent is None
    sent, marked = card(second)
    assert sent.quote == "USD" and sent.fee_asset == "USD"
    assert marked.marks.on(Field.QUOTE_ASSET_ID) is None


# --- rows 14 and 15: money not said, or not settled ------------------------------------------


def test_row_14_no_word_for_money_leaves_both_moneys_empty_and_the_price_not_compared() -> None:
    said = one("今天上午10点买了0.1个ETH，价格2600，手续费0", ETH | {"price": "2600", "fee": "0"})

    sent, marked = card(said)
    assert (sent.quote, sent.fee_asset) == (None, None)
    assert sent.fee == Decimal(0)
    assert marked.marks.on(Field.QUOTE_ASSET_ID) is None
    assert marked.marks.on(Field.FEE_ASSET_ID) is None
    assert marked.price.verdict is PriceVerdict.NO_MONEY
    assert EMPTY in said.reply and NOT_COMPARED in said.reply


def eth_ledger(*extra: tuple[str, object]) -> FakeLedger:
    """ETH bought for USDT and for US dollars on 2026-08-03; ETH's market price 2701 USDT."""
    trades = (
        *JIA_TRADES,
        ("t-eth-usd", bought("ETH", "USD", (2026, 8, 3, 15, 0))),
        *extra,
    )
    return FakeLedger(
        assets=JIA_ASSETS, trades=trades, prices={("ETH", "USDT"): Decimal(2701)}
    ).taking_cards()


ETH_30_DAO = {
    "side": "buy",
    "coin": "ETH",
    "total": "30刀",
    "price": "240",
    "fee": "0",
    "time": "今天10点",
}


def test_row_15_dao_on_a_day_that_used_both_moneys_is_empty_and_suspicious() -> None:
    said = one("今天10点花了30刀买了ETH，均价240，手续费0", ETH_30_DAO, eth_ledger())

    sent, marked = card(said)
    assert (sent.quote, sent.fee_asset) == (None, None)
    quote = mark_on(marked.marks, Field.QUOTE_ASSET_ID)
    assert quote.kind is MarkKind.SUSPICIOUS
    assert quote.reason is not None and "used both" in quote.reason
    assert Doubt.of(quote.reason) is Doubt.MONEY_TWO_USED
    assert marked.marks.on(Field.PRICE) is None
    assert marked.price.verdict is PriceVerdict.NO_MONEY
    assert sent.quantity == Decimal("0.125")
    assert EMPTY in said.reply and NOT_COMPARED in said.reply


def test_row_15b_dao_when_eth_was_last_traded_in_cny_is_empty_and_says_cny() -> None:
    cny = asset("CNY", AssetKind.CASH, Pricing.CAN_PRICE)
    trades = (*JIA_TRADES, ("t-eth-cny", bought("ETH", "CNY", (2026, 8, 9, 10, 0))))
    ledger = FakeLedger(assets=(*JIA_ASSETS, cny), trades=trades).taking_cards()
    said = one("今天10点花了30刀买了ETH，均价2400，手续费0", ETH_30_DAO | {"price": "2400"}, ledger)

    sent, marked = card(said)
    assert sent.quote is None
    quote = mark_on(marked.marks, Field.QUOTE_ASSET_ID)
    assert quote.reason is not None and "CNY" in quote.reason
    assert Doubt.of(quote.reason) is Doubt.MONEY_OTHER_USED
    assert EMPTY in said.reply


def test_row_15c_dao_when_the_ledger_cannot_be_asked_is_still_asked() -> None:
    ledger = FailingTrades(assets=JIA_ASSETS, trades=JIA_TRADES).taking_cards()
    (said,), _ = talk(
        "今天10点花了30刀买了ETH，均价240，手续费0", rows=[row(**ETH_30_DAO)], ledger=ledger
    )

    asked(said, ledger, "pricing currency")


def test_row_15d_a_fee_in_dao_follows_the_usdt_said_with_the_price() -> None:
    said = one(
        "今天10点买了0.1个ETH，均价2400 USDT，手续费1刀",
        ETH | {"time": "今天10点", "price": "2400 USDT", "fee": "1刀"},
        eth_ledger(),
    )

    sent, marked = card(said)
    assert (sent.quote, sent.fee_asset) == ("USDT", "USDT")
    assert marked.marks.on(Field.QUOTE_ASSET_ID) is None
    assert marked.marks.on(Field.FEE_ASSET_ID) is None


def test_row_15d_a_fee_in_dao_with_no_money_said_elsewhere_leaves_both_empty_and_suspicious() -> (
    None
):
    said = one(
        "今天10点买了0.1个ETH，均价2400，手续费1刀",
        ETH | {"time": "今天10点", "price": "2400", "price_currency": "刀", "fee": "1刀"},
        eth_ledger(),
    )

    sent, marked = card(said)
    assert (sent.quote, sent.fee_asset) == (None, None)
    for field in (Field.QUOTE_ASSET_ID, Field.FEE_ASSET_ID):
        assert mark_on(marked.marks, field).kind is MarkKind.SUSPICIOUS


# --- rows 22 to 26: a cell said, but wrong in itself ------------------------------------------


def test_row_22_a_price_of_0_is_empty_and_suspicious_with_the_0() -> None:
    said = one(
        "今天上午10点买了0.1个ETH，价格0 USDT，手续费0", ETH | {"price": "0 USDT", "fee": "0"}
    )

    sent, marked = card(said)
    assert (sent.price, sent.total) == (None, None)
    price = mark_on(marked.marks, Field.PRICE)
    assert price.kind is MarkKind.SUSPICIOUS
    assert price.reason == "you said the price was 0, which is not above zero"
    assert wire(sent)["price"] == ("suspicious", price.reason)
    assert EMPTY in said.reply


def test_row_23_a_day_after_today_is_empty_and_suspicious_and_no_time_is_sent() -> None:
    said = one(
        "明天上午10点买了0.1个ETH，价格2600 USDT，手续费0",
        ETH | {"time": "明天上午10点", "price": "2600 USDT", "fee": "0"},
    )

    sent, marked = card(said)
    assert sent.occurred is None and sent.zone is None
    day = mark_on(marked.marks, Field.OCCURRED_DATE)
    assert day.reason is not None and "2026-11-25" in day.reason and "after today" in day.reason
    assert not {"occurredTime", "occurredTimeZone"} & set(wire(sent))
    assert EMPTY in said.reply


def test_row_24_a_fee_not_below_the_quantity_keeps_the_quantity_and_empties_the_fee() -> None:
    said = one(
        "今天上午10点买了0.001个BTC，价格60000 USDT，手续费0.002 BTC",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "0.001个BTC",
            "price": "60000 USDT",
            "fee": "0.002 BTC",
            "time": "今天上午10点",
        },
    )

    sent, marked = card(said)
    assert sent.quantity == Decimal("0.001") and sent.fee is None
    for field in (Field.QUANTITY, Field.FEE):
        reason = mark_on(marked.marks, field).reason
        assert reason is not None and "0.001" in reason and "0.002" in reason
    assert EMPTY in said.reply


def test_row_25_a_platform_too_long_is_not_sent_and_suspicious() -> None:
    long = "一个特别长的平台名字" * 20
    said = one(
        f"今天上午10点在{long}买了0.1个ETH，价格2600 USDT，手续费0",
        ETH | {"price": "2600 USDT", "fee": "0", "platform": long},
    )

    sent, marked = card(said)
    assert sent.platform == ""
    platform = mark_on(marked.marks, Field.PLATFORM)
    assert platform.reason is not None and "longer than the ledger allows" in platform.reason
    assert long[:5] in platform.reason
    assert wire(sent)["platform"][0] == "suspicious"


def test_row_26_disagreeing_and_far_is_one_suspicious_price_mark_disagreement_first() -> None:
    cells = SOL_200 | {"price": "21.2 USDT"}
    said = one("今天上午8:25花了200 USDT买入了0.094326个SOL，均价21.2 USDT，手续费0", cells)

    sent, marked = card(said)
    price = mark_on(marked.marks, Field.PRICE)
    assert price.kind is MarkKind.SUSPICIOUS
    assert price.reason is not None
    assert price.reason.index(NOT_GUESSED) < price.reason.index(FAR)
    assert len([mark for mark in sent.marks if mark.field == "price"]) == 1
    assert sent.total == Decimal("200")
    assert NOT_GUESSED in said.reply and FAR in said.reply


# --- row 27: a ledger from before still gets every question ----------------------------------


def test_row_27_a_ledger_that_takes_no_card_is_asked_the_fee_and_sent_no_marks() -> None:
    ledger = demo_ledger()
    (said,), _ = talk(
        "今天上午10点买了0.1个ETH，价格2600 USDT",
        rows=[row(**(ETH | {"price": "2600 USDT"}))],
        ledger=ledger,
    )

    asked(said, ledger, "fee")


# --- rows 16 to 20: as before ----------------------------------------------------------------


def test_row_16_tesla_is_as_before_on_a_ledger_that_takes_cards_and_one_that_does_not() -> None:
    words = "今天下午买了2股特斯拉，每股300美元，手续费1美元"
    cells = {"side": "buy", "coin": "特斯拉", "quantity": "2股", "price": "300美元",
             "fee": "1美元", "time": "今天下午"}  # fmt: skip
    before = one(words, cells, demo_ledger())
    now = one(words, cells)

    assert now.reply == before.reply
    assert now.sent is None
    assert now.recorded is not None and before.recorded is not None
    assert now.recorded.ending is before.recorded.ending


def test_row_17_two_trades_one_whole_and_one_with_no_fee_are_two_cards() -> None:
    (said,), _ = talk(
        "今天上午10点买了0.01个BTC，价格60000 USDT，手续费0；还买了0.1个ETH，价格2600 USDT",
        rows=[
            row(side="buy", coin="BTC", quantity="0.01个BTC", price="60000 USDT", fee="0",
                time="今天上午10点"),
            row(**(ETH | {"price": "2600 USDT"})),
        ],
    )  # fmt: skip

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    first, second = said.recorded.checks
    assert first.ready is True
    assert second.ready is False and second.missing == ("fee", "feeAssetId")
    assert "Trade 2 was sent with empty fields" in said.reply
    assert "Trade 1 was sent with empty fields" not in said.reply


SELL_5 = {
    "side": "sell",
    "coin": "BTC",
    "quantity": "5个BTC",
    "price": "60000 USDT",
    "time": "今天上午9点",
}


def test_row_18_selling_more_than_held_with_no_fee_carries_the_ledgers_own_words() -> None:
    said = one("今天上午9点卖了5个BTC，价格60000 USDT", SELL_5)

    sent, _ = card(said)
    assert said.recorded is not None
    (check,) = said.recorded.checks
    assert check.problem is not None and check.problem.code == "INSUFFICIENT_HOLDINGS"
    assert EMPTY in said.reply
    assert check.problem.message in said.reply


def test_row_19_selling_more_than_held_with_every_cell_is_turned_down_as_before() -> None:
    said = one("今天上午9点卖了5个BTC，价格60000 USDT，手续费0", SELL_5 | {"fee": "0"})

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.LEDGER_REFUSED
    (check,) = said.recorded.checks
    assert check.outcome is CheckOutcome.FAILED


# --- the words said when the ledger could not check in full ----------------------------------


def test_a_sell_with_no_price_is_never_said_to_have_nothing_wrong() -> None:
    said = one(
        "今天上午9点卖了0.1个BTC，手续费0",
        SELL_5 | {"quantity": "0.1个BTC", "price": "", "fee": "0"},
    )

    card(said)
    assert "cannot check it in full while price, totalValue" in said.reply
    assert "Whether you held enough to sell can be checked only once" in said.reply
    assert "no problem" not in said.reply.lower()


# --- saving a card with an empty cell, in the demo ledger -------------------------------------


def test_a_card_with_an_empty_cell_cannot_be_saved_and_the_book_stays() -> None:
    (said,), ledger = talk(
        "今天上午10点买了0.1个ETH，价格2600 USDT", rows=[row(**(ETH | {"price": "2600 USDT"}))]
    )

    assert said.sent is not None
    before = len(ledger.list_trades(_ALL).trades)
    done = demo_save(ledger, said.sent.proposals[0])
    assert done.outcome is DemoOutcome.FAILED
    assert done.failure is not None and "fee, feeAssetId" in done.failure.message
    assert len(ledger.list_trades(_ALL).trades) == before


_ALL = TradeFilter()


# --- what leaves for the ledger, for every row that sends a card ------------------------------

SENT_ROWS = {
    "2 no fee": ("今天上午10点买了0.1个ETH，价格2600 USDT", ETH | {"price": "2600 USDT"}),
    "3 no fee money": (
        "今天上午10点买了0.1个ETH，价格2600 USDT，手续费0.5",
        ETH | {"price": "2600 USDT", "fee": "0.5"},
    ),
    "4 no time": (
        "买了0.1个ETH，价格2600 USDT，手续费0",
        {"side": "buy", "coin": "ETH", "quantity": "0.1个ETH", "price": "2600 USDT", "fee": "0"},
    ),
    "6 25U": (
        "今天上午10点用25U买了点ETH，手续费0",
        {"side": "buy", "coin": "ETH", "quantity": "25U", "fee": "0", "time": "今天上午10点"},
    ),
    "7 no price": ("今天上午10点买了0.1个ETH，手续费0", ETH | {"fee": "0"}),
    "9 disagree": (
        "今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT，手续费0",
        SOL_200,
    ),
    "14 no money": (
        "今天上午10点买了0.1个ETH，价格2600，手续费0",
        ETH | {"price": "2600", "fee": "0"},
    ),
    "22 price 0": (
        "今天上午10点买了0.1个ETH，价格0 USDT，手续费0",
        ETH | {"price": "0 USDT", "fee": "0"},
    ),
    "23 tomorrow": (
        "明天上午10点买了0.1个ETH，价格2600 USDT，手续费0",
        ETH | {"time": "明天上午10点", "price": "2600 USDT", "fee": "0"},
    ),
    "24 fee not below": (
        "今天上午10点买了0.001个BTC，价格60000 USDT，手续费0.002 BTC",
        {"side": "buy", "coin": "BTC", "quantity": "0.001个BTC", "price": "60000 USDT",
         "fee": "0.002 BTC", "time": "今天上午10点"},
    ),
    "26 disagree and far": (
        "今天上午8:25花了200 USDT买入了0.094326个SOL，均价21.2 USDT，手续费0",
        SOL_200 | {"price": "21.2 USDT"},
    ),
}  # fmt: skip


@pytest.mark.parametrize(("words", "cells"), SENT_ROWS.values(), ids=SENT_ROWS.keys())
def test_what_the_ledger_is_handed_keeps_its_rules_and_no_empty_cell_is_0(
    words: str, cells: dict[str, str]
) -> None:
    (said,), ledger = talk(words, rows=[row(**cells)])

    sent, _ = card(said)
    assert said.sent is not None
    kept = ledger.card_of(said.sent.proposals[0])
    assert kept == sent
    for name, value in {
        "quantity": sent.quantity, "price": sent.price, "totalValue": sent.total,
        "quoteAssetId": sent.quote, "fee": sent.fee, "feeAssetId": sent.fee_asset,
    }.items():  # fmt: skip
        if name in sent.missing:
            assert value is None
        assert value != ""
    fields = [one.field for one in sent.marks]
    assert len(fields) == len(set(fields))
    for one in sent.marks:
        assert one.kind in {"computed", "inferred", "suspicious"}
        if one.field in sent.missing or one.field in {"occurredTime", "occurredTimeZone"}:
            assert one.kind == "suspicious"
        if one.kind == "suspicious":
            assert one.reason is not None and one.reason.strip()
            # Only the kinds this program names: far from the market price, or a Doubt.
            assert FAR in one.reason or Doubt.of(one.reason) is not None, one.reason
        if one.reason is not None:
            assert reason_length(one.reason) <= REASON_MOST
        assert set(one.as_dict()) == {"field", "kind", "reason"}


# --- the record kept on this machine, rows 2 and 9 --------------------------------------------


def test_the_record_keeps_a_cards_empty_cells_as_null_and_names_them() -> None:
    words = "今天上午10点买了0.1个ETH，价格2600 USDT"
    said = one(words, ETH | {"price": "2600 USDT"})

    entry = entry_for(said, words=words, at=INVENTED_NOW, model="invented-model")

    (trade,) = entry["trades"]
    assert (trade["fee"], trade["fee_asset"]) == (None, None)
    (kept,) = entry["marks"]
    assert kept["empty"] == ["fee", "feeAssetId"]
    assert json.loads(json.dumps(entry)) == entry


def test_the_record_keeps_the_three_suspicious_marks_of_figures_that_disagree() -> None:
    words = "今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT，手续费0"
    said = one(words, SOL_200)

    entry = entry_for(said, words=words, at=INVENTED_NOW, model="invented-model")

    (trade,) = entry["trades"]
    assert trade["total"] == "200" and trade["quantity"] == "0.094326"
    (kept,) = entry["marks"]
    assert kept["empty"] == []
    assert {(one["field"], one["kind"]) for one in kept["marks"]} == {
        ("quantity", "suspicious"),
        ("price", "suspicious"),
        ("totalValue", "suspicious"),
    }


# --- the try-out script -------------------------------------------------------------------------


def test_the_try_out_script_prints_none_for_an_empty_cell_and_one_line_more() -> None:
    words = "今天上午10点买了0.1个ETH，价格2600 USDT"
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "ETH"))],
        extraction=[table(row(**(ETH | {"price": "2600 USDT"})))],
    )
    out = io.StringIO()

    status = try_assistant.main([words], out=out, model=model, max_steps=6)

    printed = out.getvalue()
    assert status == 0
    assert "buy 0.1 ETH at 2600 USDT, total 260 USDT, fee none none" in printed
    assert "    empty: fee, feeAssetId; the ledger: cannot be saved yet" in printed
    assert "money: price said, fee empty" in printed


def test_one_empty_cell_the_ledger_would_check_is_said_with_is() -> None:
    said = one(
        "明天上午10点买了0.1个ETH，价格2600 USDT，手续费0",
        ETH | {"time": "明天上午10点", "price": "2600 USDT", "fee": "0"},
    )

    assert "cannot check it in full while occurredDate is empty" in said.reply


def test_a_price_left_empty_is_said_as_not_compared_for_that_reason() -> None:
    said = one("今天上午10点买了0.1个ETH，手续费0", ETH | {"fee": "0"})

    _, marked = card(said)
    assert price_check_words(marked.price) == "not compared: the price is left empty"
    assert NOT_COMPARED not in said.reply
