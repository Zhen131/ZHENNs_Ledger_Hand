"""Tests of the marks on each trade the assistant sends, one for each row of the table of examples.

The demo book, "now" its fixed moment (24 November 2026, 23:55 in
Budapest), five times apart counted as far unless a row says otherwise.
Market prices: BTC 64880 USDT, ETH 2701 USDT, MSFT 441.62 USD, SOL 150
USDT, INTC 24 USD, KO 70 USD, AAPL 230 USD, NVDA 130 USD; ADA, PEP and DOT
none. A scripted model stands in for every call, and its table of what it
read is written out in each test. Every sentence and number is invented.

The marks stay on this side: what is sent to the ledger is the trade as
before, and a test of each row checks the figures sent.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.marks import FAR_REASON_START, Field, FieldMark, MarkKind, TradeMarks
from ledger_hand.core.price_check import PriceVerdict
from ledger_hand.flows import conversation
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import MarkedTrade, RecordEnding
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES, DEMO_TRADES, demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_conversation_asset_pick import pick

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
FAR = "far from the market price"
NOT_COMPARED = "not compared with the market price"
GUESS = "This is a guess"


def send(
    words: str,
    cells: dict[str, str],
    *,
    ledger: FakeLedger | None = None,
    gap: Decimal = Decimal(5),
    picks: tuple[str, ...] = (),
) -> tuple[Said, FakeLedger]:
    """What comes of saying ``words``, the model reading ``cells`` from them."""
    ledger = ledger if ledger is not None else demo_ledger()
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", cells["coin"]))],
        extraction=[table(row(**cells))],
        picks=picks,
    )
    said = say(
        AssistantChat(),
        words,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        price_gap=gap,
    )
    return said, ledger


def sent_one(said: Said) -> tuple[TradeFacts, MarkedTrade]:
    """The one trade sent, and its marks; the proposal waits in the ledger."""
    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT, said.reply
    (trade,) = recorded.trades
    (marked,) = recorded.marked
    return trade, marked


def kinds(marks: TradeMarks) -> dict[Field, MarkKind]:
    return {mark.field: mark.kind for mark in marks.marks}


def mark_on(marks: TradeMarks, field: Field) -> FieldMark:
    found = marks.on(field)
    assert found is not None, marks
    return found


def btc_buy(price: str) -> dict[str, str]:
    return {
        "side": "buy",
        "coin": "BTC",
        "quantity": "0.01个BTC",
        "price": price,
        "fee": "0",
        "time": "今天上午10点",
    }


def btc_words(price: str) -> str:
    return f"今天上午10点买了0.01个BTC，价格{price}，手续费0"


def btc_said(price: str, **options: object) -> tuple[Said, FakeLedger]:
    return send(btc_words(price), btc_buy(price), **options)  # type: ignore[arg-type]


ROW_1_WORDS = "今天上午11点在币安0.01个BTC 花了950U，手续费0"
ROW_1_CELLS = {
    "side": "buy",
    "coin": "BTC",
    "quantity": "0.01个BTC",
    "price": "950U",
    "fee": "0",
    "time": "今天上午11点",
    "platform": "币安",
}


# --- row 1: the fourth sentence ---------------------------------------------------------


def test_row_01_950u_as_the_price_is_suspicious_and_the_total_worked_out() -> None:
    said, _ = send(ROW_1_WORDS, ROW_1_CELLS)

    trade, marked = sent_one(said)
    assert (trade.quantity, trade.price, trade.total, trade.quote) == (
        Decimal("0.01"),
        Decimal("950"),
        Decimal("9.50"),
        "USDT",
    )
    assert kinds(marked.marks) == {
        Field.PRICE: MarkKind.SUSPICIOUS,
        Field.TOTAL_VALUE: MarkKind.COMPUTED,
    }
    reason = mark_on(marked.marks, Field.PRICE).reason or ""
    assert reason.startswith(FAR_REASON_START)
    assert "64880" in reason and "USDT" in reason
    assert marked.price.verdict is PriceVerdict.FAR
    assert FAR in said.reply
    assert "about 68 times lower" in said.reply


# --- rows 2 to 5: the line at five times, both ways ---------------------------------


def test_row_02_exactly_a_fifth_of_the_market_price_is_far() -> None:
    said, _ = btc_said("12976 USDT")

    _, marked = sent_one(said)
    assert mark_on(marked.marks, Field.PRICE).kind is MarkKind.SUSPICIOUS
    assert FAR in said.reply


def test_row_03_just_above_a_fifth_is_not_marked() -> None:
    said, _ = btc_said("12977 USDT")

    _, marked = sent_one(said)
    assert kinds(marked.marks) == {Field.TOTAL_VALUE: MarkKind.COMPUTED}
    assert marked.price.verdict is PriceVerdict.WITHIN
    assert FAR not in said.reply


def test_row_04_exactly_five_times_the_market_price_is_far_and_higher() -> None:
    said, _ = btc_said("324400 USDT")

    _, marked = sent_one(said)
    assert mark_on(marked.marks, Field.PRICE).kind is MarkKind.SUSPICIOUS
    assert FAR in said.reply
    assert "times higher" in said.reply


def test_row_05_just_below_five_times_is_not_marked() -> None:
    said, _ = btc_said("324399 USDT")

    _, marked = sent_one(said)
    assert marked.marks.on(Field.PRICE) is None
    assert FAR not in said.reply


# --- rows 6 and 7: nothing to compare with ------------------------------------------------


def test_row_06_an_asset_with_no_market_price_is_not_spoken_of() -> None:
    cells = {
        "side": "buy",
        "coin": "ADA",
        "quantity": "100个ADA",
        "price": "5 USDT",
        "fee": "0",
        "time": "今天上午10点",
    }
    said, _ = send("今天上午10点买了100个ADA，价格5 USDT，手续费0", cells)

    _, marked = sent_one(said)
    assert marked.marks.on(Field.PRICE) is None
    assert marked.price.verdict is PriceVerdict.NO_MARKET_PRICE
    assert "market price" not in said.reply


ETH_2600 = "今天上午10点买了0.1个ETH，成交价2600 USDT，手续费0"
ETH_2600_CELLS = {
    "side": "buy",
    "coin": "ETH",
    "quantity": "0.1个ETH",
    "price": "2600 USDT",
    "fee": "0",
    "time": "今天上午10点",
}


def test_row_07_a_market_price_in_another_money_is_not_compared_and_said_so() -> None:
    ledger = FakeLedger(
        assets=DEMO_ASSETS, trades=DEMO_TRADES, prices={("ETH", "USD"): Decimal("2700")}
    )
    said, _ = send(ETH_2600, ETH_2600_CELLS, ledger=ledger)

    trade, marked = sent_one(said)
    assert trade.quote == "USDT"
    assert marked.marks.on(Field.PRICE) is None
    assert marked.price.verdict is PriceVerdict.OTHER_MONEY
    (line,) = [line for line in said.reply.splitlines() if NOT_COMPARED in line]
    assert "USDT" in line and "USD," in line


def test_row_07b_dollars_against_a_market_price_in_usdt_are_not_compared() -> None:
    cells = ETH_2600_CELLS | {"price": "2600美元"}
    said, _ = send("今天上午10点买了0.1个ETH，价格2600美元，手续费0", cells)

    recorded = said.recorded
    assert recorded is not None
    if recorded.ending is RecordEnding.SENT:
        _, marked = sent_one(said)
        assert marked.price.verdict is PriceVerdict.OTHER_MONEY
        assert marked.marks.on(Field.PRICE) is None
        assert NOT_COMPARED in said.reply
    else:
        assert "market price" not in said.reply


def test_row_07c_a_market_price_of_zero_is_no_market_price() -> None:
    ledger = FakeLedger(
        assets=DEMO_ASSETS, trades=DEMO_TRADES, prices={("BTC", "USDT"): Decimal("0")}
    )
    said, _ = btc_said("950 USDT", ledger=ledger)

    _, marked = sent_one(said)
    assert marked.marks.on(Field.PRICE) is None
    assert marked.price.verdict is PriceVerdict.NO_MARKET_PRICE
    assert "market price" not in said.reply


# --- rows 8 to 10: assumed by the program ---------------------------------------------------


def eth_for_30(price: str) -> tuple[Said, FakeLedger]:
    cells = {
        "side": "buy",
        "coin": "ETH",
        "total": "30美金",
        "price": price,
        "fee": "0",
        "time": "今天上午10点",
    }
    return send(f"今天上午10点花了30美金买了ETH，均价{price}，手续费0", cells)


def test_row_08_the_money_guessed_is_assumed_and_the_quantity_worked_out() -> None:
    said, _ = eth_for_30("2400")

    trade, marked = sent_one(said)
    assert (trade.quantity, trade.quote) == (Decimal("0.0125"), "USDT")
    # A fee of 0 is taken in the money traded: only that money was guessed.
    assert kinds(marked.marks) == {
        Field.QUANTITY: MarkKind.COMPUTED,
        Field.QUOTE_ASSET_ID: MarkKind.INFERRED,
    }
    reason = mark_on(marked.marks, Field.QUOTE_ASSET_ID).reason or ""
    assert "USDT" in reason and "2026-11-19" in reason
    assert GUESS in said.reply
    assert FAR not in said.reply


def test_row_09_all_three_kinds_on_one_trade() -> None:
    said, _ = eth_for_30("240")

    trade, marked = sent_one(said)
    assert trade.quantity == Decimal("0.125")
    found = kinds(marked.marks)
    assert found[Field.QUOTE_ASSET_ID] is MarkKind.INFERRED
    assert found[Field.QUANTITY] is MarkKind.COMPUTED
    assert found[Field.PRICE] is MarkKind.SUSPICIOUS
    assert "about 11 times lower" in said.reply
    assert GUESS in said.reply


def test_row_10_an_asset_the_model_matched_is_assumed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation, "ASSISTANT_PICKS_ASSETS", True)
    cells = {
        "side": "buy",
        "coin": "微软的股票",
        "quantity": "1.5股",
        "price": "412.5美元",
        "fee": "0",
        "time": "今天15:30",
    }
    said, _ = send(
        "今天15:30买了1.5股微软的股票，一股412.5美元，手续费0",
        cells,
        picks=(pick("微软", "MSFT"),),
    )

    trade, marked = sent_one(said)
    assert (trade.asset, trade.total) == ("MSFT", Decimal("618.750"))
    found = kinds(marked.marks)
    assert found[Field.ASSET_ID] is MarkKind.INFERRED
    assert found[Field.TOTAL_VALUE] is MarkKind.COMPUTED
    assert Field.PRICE not in found
    reason = mark_on(marked.marks, Field.ASSET_ID).reason or ""
    assert "微软" in reason and "MSFT" in reason and "Microsoft" in reason
    assert 'Took "微软" as MSFT' in said.reply


# --- rows 11 to 17 ---------------------------------------------------------------------------


def test_row_11_a_share_at_exactly_five_times_is_far() -> None:
    cells = {
        "side": "buy",
        "coin": "KO",
        "quantity": "2股KO",
        "price": "350美元",
        "fee": "1美元",
        "time": "今天16:00",
    }
    said, _ = send("今天16:00买了2股KO，每股350美元，手续费1美元", cells)

    _, marked = sent_one(said)
    assert mark_on(marked.marks, Field.PRICE).kind is MarkKind.SUSPICIOUS
    assert FAR in said.reply


def test_row_12_a_ledger_that_cannot_be_asked_for_prices_still_gets_the_trade() -> None:
    failure = LedgerError(LedgerErrorKind.TIMED_OUT, "timed_out", "The ledger did not answer.")
    ledger = FakeLedger(
        assets=DEMO_ASSETS, trades=DEMO_TRADES, prices=DEMO_MARKET_PRICES, market_failure=failure
    )
    said, ledger = send(ROW_1_WORDS, ROW_1_CELLS, ledger=ledger)

    trade, marked = sent_one(said)
    assert trade.price == Decimal("950")
    assert marked.marks.on(Field.PRICE) is None
    assert marked.price.verdict is PriceVerdict.NOT_ASKED
    (line,) = [line for line in said.reply.splitlines() if NOT_COMPARED in line]
    assert "The ledger did not answer." in line
    assert ledger.calls == ["list_assets", "market_prices", "propose_add"]


@pytest.mark.parametrize(("gap", "marked_far"), [(Decimal(3), True), (Decimal(5), False)])
def test_row_13_the_line_follows_the_setting(gap: Decimal, marked_far: bool) -> None:
    said, _ = btc_said("20000 USDT", gap=gap)

    _, marked = sent_one(said)
    assert (marked.marks.on(Field.PRICE) is not None) is marked_far
    assert (FAR in said.reply) is marked_far


def test_row_14_a_sell_has_its_total_worked_out_and_nothing_else() -> None:
    cells = {
        "side": "sell",
        "coin": "BTC",
        "quantity": "0.1个BTC",
        "price": "60000 USDT",
        "fee": "0",
        "time": "今天上午9点",
    }
    said, _ = send("今天上午9点卖了0.1个BTC，价格60000 USDT，手续费0", cells)

    trade, marked = sent_one(said)
    assert trade.total == Decimal("6000.0")
    assert kinds(marked.marks) == {Field.TOTAL_VALUE: MarkKind.COMPUTED}
    assert FAR not in said.reply


def test_row_15_both_moneys_guessed_are_assumed() -> None:
    cells = {
        "side": "buy",
        "coin": "MSFT",
        "quantity": "3股MSFT",
        "price": "400刀",
        "fee": "1刀",
        "time": "今天15:30",
    }
    said, _ = send("今天15:30买了3股MSFT，每股400刀，手续费1刀", cells)

    trade, marked = sent_one(said)
    assert (trade.quote, trade.fee_asset, trade.total) == ("USD", "USD", Decimal("1200"))
    assert kinds(marked.marks) == {
        Field.TOTAL_VALUE: MarkKind.COMPUTED,
        Field.QUOTE_ASSET_ID: MarkKind.INFERRED,
        Field.FEE_ASSET_ID: MarkKind.INFERRED,
    }
    assert "its fee is taken in USD" in said.reply


def test_row_16_a_price_worked_out_and_far_is_suspicious_saying_it_was_worked_out() -> None:
    cells = {
        "side": "buy",
        "coin": "BTC",
        "quantity": "10个BTC",
        "total": "950U",
        "fee": "0",
        "time": "今天10点",
    }
    said, _ = send("今天10点花了950U买了10个BTC，手续费0", cells)

    trade, marked = sent_one(said)
    assert trade.price == Decimal("95")
    assert kinds(marked.marks) == {Field.PRICE: MarkKind.SUSPICIOUS}
    reason = mark_on(marked.marks, Field.PRICE).reason or ""
    assert reason.startswith("worked out")
    assert FAR_REASON_START in reason
    assert FAR in said.reply


def test_row_17_a_trade_known_only_to_its_day_is_sent_with_no_mark_on_its_time() -> None:
    cells = {
        "side": "buy",
        "coin": "ETH",
        "quantity": "0.1个ETH",
        "price": "2600 USDT",
        "fee": "0",
        "time": "11月20号",
    }
    said, _ = send("11月20号买了0.1个ETH，价格2600 USDT，手续费0", cells)

    trade, marked = sent_one(said)
    assert trade.date_only
    assert trade.day == date(2026, 11, 20)
    assert trade.total == Decimal("260.0")
    assert kinds(marked.marks) == {Field.TOTAL_VALUE: MarkKind.COMPUTED}
    assert "has no time of day" not in said.reply


# --- the reverse: no far line without a suspicious mark ---------------------------------


@pytest.mark.parametrize("price", ["12977 USDT", "324399 USDT", "64880 USDT"])
def test_a_trade_with_no_suspicious_mark_is_never_said_to_be_far(price: str) -> None:
    said, _ = btc_said(price)

    _, marked = sent_one(said)
    assert all(mark.kind is not MarkKind.SUSPICIOUS for mark in marked.marks.marks)
    assert FAR not in said.reply
