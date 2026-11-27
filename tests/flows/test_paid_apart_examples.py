"""Tests of trades paid in one money for an asset the ledger prices in another, said aloud.

One test for each line of the table of examples the rule was settled with
(87B, part 4, item 8), numbered as there; the ledgers are made in
``paid_apart_books``, and E1 and E3 are said once more against the demo
ledger with a euro. A scripted model stands in for every call. Every
sentence, reply and number is invented.

The rule: a trade whose asset the ledger prices in A, whose total names
another money P the ledger prices trades in, and where P and A are not
USDT and the US dollar, is sent paid in P, its price the total over the
quantity, with the rate worked out from the price said in A. Anything else
goes on as before. A row marked "as before" asserts what the program did
on the same sentence before this rule, measured on 2026-11-26.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from decimal import Decimal

from ledger_hand.core.cost_rate import rate_of
from ledger_hand.core.marks import MarkKind
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.ledger.demo_euro import demo_ledger_with_euro
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows import paid_apart_books as books
from tests.flows.scripted_flow import copied, row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
NO_FX_FEE = "without any FX fee"
GUESS = "This is a guess"
NO_REFERENCE = "was not compared with one"

KO = {"side": "buy", "coin": "KO", "quantity": "2股", "time": "今天15:30"}
E1 = "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元"
E1_ROW = KO | {"price": "69.5美元", "total": "128欧元", "fee": "0.19欧元"}
E3 = "今天15:30花了128欧元买了2股KO，一股69.5美金，换汇费0.19欧元"
E3_ROW = KO | {"price": "69.5美金", "total": "128欧元", "fee": "0.19欧元"}
E16 = "今天15:30花了128欧元买了2股KO，换汇费0.19欧元"
E16_ROW = KO | {"total": "128欧元", "fee": "0.19欧元"}
E17 = "今天15:30花了128欧元买了2股KO，一股64欧元，也就是69.5美元，换汇费0.19欧"
PEP = {"side": "buy", "coin": "PEP", "quantity": "1股", "total": "160美元", "fee": "0"}


def talk(
    *said: str,
    rows: Sequence[dict[str, str]],
    ledger: FakeLedger,
    answers: Sequence[str] = (),
) -> list[Said]:
    """Each thing said in one chat; the scripted model copies each answer read by the model."""
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said[0][:6]))],
        extraction=[table(*(row(**cells) for cells in rows))],
        answers=list(answers),
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
    return seen


def one(said: str, cells: dict[str, str], ledger: FakeLedger) -> Said:
    (result,) = talk(said, rows=[cells], ledger=ledger)
    return result


def sent(said: Said) -> tuple[TradeCard, ...]:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT, said.reply
    return said.recorded.trades


def mark_on(card: TradeCard, field: str) -> tuple[str, str | None] | None:
    found = [(mark.kind, mark.reason) for mark in card.marks if mark.field == field]
    return found[0] if found else None


def asked(said: Said, label: str) -> None:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING, said.reply
    assert said.reply.startswith(label), said.reply
    assert said.sent is None


def nothing_paid_apart(said: Said) -> None:
    """Nothing was sent this way: no rate on any trade, no word of an FX fee."""
    assert said.recorded is not None
    assert all(card.cost_rate is None for card in said.recorded.trades)
    assert all(marked.rate is None for marked in said.recorded.marked)
    assert NO_FX_FEE not in said.reply


def like_e1(card: TradeCard, fee: str = "0.19") -> None:
    assert (card.asset, card.quote, card.fee_asset) == ("KO", "EUR", "EUR")
    assert (card.quantity, card.price, card.total) == (Decimal(2), Decimal(64), Decimal(128))
    assert card.fee == Decimal(fee)
    assert card.cost_rate == Decimal("1.0859375")
    assert mark_on(card, "price") == (
        MarkKind.COMPUTED.value,
        "worked out as total ÷ quantity, in EUR",
    )
    kind, reason = mark_on(card, "costRate") or ("", "")
    assert kind == MarkKind.COMPUTED.value
    assert reason is not None and "69.5 USD" in reason
    assert mark_on(card, "totalValue") is None


# --- E1 to E3: sent, the rate worked out ----------------------------------------------


def test_e1_euros_for_shares_priced_in_dollars_are_sent_with_the_rate() -> None:
    said = one(E1, E1_ROW, books.jia())

    (card,) = sent(said)
    like_e1(card)
    assert NO_FX_FEE in said.reply
    assert GUESS not in said.reply
    # The reference is AAPL's EUR trade at 1.0859: less than ten in a hundred away.
    assert NO_REFERENCE not in said.reply and "is far from" not in said.reply
    assert said.recorded is not None
    (marked,) = said.recorded.marked
    assert marked.rate is not None and marked.rate.reference is not None
    assert (marked.rate.reference.rate, marked.rate.reference.asset) == (Decimal("1.0859"), "AAPL")


def test_e2_a_price_that_does_not_divide_evenly_is_rounded_and_the_rate_is_one_point_086() -> None:
    said = one(
        "今天15:30花了100欧元买了3股KO，一股36.2美元，手续费0",
        KO | {"quantity": "3股", "price": "36.2美元", "total": "100欧元", "fee": "0"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.price, card.total, card.quote) == (Decimal("33.33333333"), Decimal(100), "EUR")
    assert abs(card.quantity * card.price - card.total) <= Decimal("0.01")  # type: ignore[operator]
    assert (card.fee, card.fee_asset) == (Decimal(0), "EUR")
    assert card.cost_rate == Decimal("1.086")


def test_e3_meijin_for_the_share_price_is_dollars_from_kos_last_trade_marked_assumed() -> None:
    said = one(E3, E3_ROW, books.jia())

    (card,) = sent(said)
    assert card.cost_rate == Decimal("1.0859375")
    kind, reason = mark_on(card, "costRate") or ("", "")
    assert kind == MarkKind.INFERRED.value
    assert reason is not None and "t-ko" in reason and "69.5 USD" in reason
    assert GUESS in said.reply and NO_FX_FEE in said.reply


def test_e1_on_the_demo_ledger_with_a_euro() -> None:
    said = one(E1, E1_ROW, demo_ledger_with_euro().taking_cards())

    (card,) = sent(said)
    like_e1(card)
    assert NO_FX_FEE in said.reply and GUESS not in said.reply
    # The demo book has no trade paid in euros: nothing to compare the rate with.
    assert NO_REFERENCE in said.reply


def test_e3_on_the_demo_ledger_with_a_euro() -> None:
    said = one(E3, E3_ROW, demo_ledger_with_euro().taking_cards())

    (card,) = sent(said)
    assert card.cost_rate == Decimal("1.0859375")
    assert (mark_on(card, "costRate") or ("",))[0] == MarkKind.INFERRED.value
    assert GUESS in said.reply and NO_FX_FEE in said.reply and NO_REFERENCE in said.reply


# --- E4 to E9: as before ----------------------------------------------------------------


E4 = "今天15:30花了210欧元买了1股AAPL，一股230美金，换汇费0.3欧元"
E4_ROW = {
    "side": "buy",
    "coin": "AAPL",
    "quantity": "1股",
    "price": "230美金",
    "total": "210欧元",
    "fee": "0.3欧元",
    "time": "今天15:30",
}


def test_e4_meijin_after_a_euro_trade_is_the_shares_own_dollars_as_a_guess() -> None:
    # Since 2026-11-27 (90A part 2 item 1): AAPL's last trade used EUR, neither
    # USDT nor USD, so "美金" is AAPL's own currency in the ledger, USD, a guess.
    ledger = books.jia()
    said = one(E4, E4_ROW, ledger)

    (card,) = sent(said)
    assert (card.asset, card.quote) == ("AAPL", "EUR")
    assert card.cost_rate == rate_of(Decimal(1), Decimal(230), Decimal(210))
    assert card.total == Decimal(210)
    kind, reason = mark_on(card, "costRate") or ("", "")
    assert kind == MarkKind.INFERRED.value
    assert reason is not None and "AAPL's own currency in the ledger, USD" in reason
    assert "used EUR" in reason
    assert GUESS in said.reply and "own currency" in said.reply


def test_e4_with_the_share_priced_in_yuan_meijin_is_asked_as_before() -> None:
    # What the old E4 held: "美金" after a euro trade is not taken as dollars
    # when nothing says so. With AAPL's own currency CNY, it is asked as before.
    assets = tuple(
        dataclasses.replace(one, price_currency="CNY") if one.code == "AAPL" else one
        for one in books.JIA_ASSETS
    )
    ledger = FakeLedger(assets=assets, trades=books.JIA_TRADES, prices=books.JIA_PRICES)
    said = one(E4, E4_ROW, ledger.taking_cards())

    asked(said, "[Trade 1 of 1: pricing currency]")
    nothing_paid_apart(said)


def test_e5_meijin_for_a_share_never_traded_is_asked_as_before() -> None:
    ledger = books.jia()
    said = one(
        "今天15:30花了150欧元买了1股PEP，一股160美金，手续费0",
        PEP | {"price": "160美金", "total": "150欧元", "time": "今天15:30"},
        ledger,
    )

    asked(said, "[Trade 1 of 1: pricing currency]")
    nothing_paid_apart(said)
    assert "propose_add" not in ledger.calls


def test_e6_no_euro_in_the_ledger_is_told_and_nothing_sent() -> None:
    said = one(E1, E1_ROW, books.yi())

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    assert "the ledger has no currency EUR yet" in said.reply
    nothing_paid_apart(said)


def test_e7_a_euro_that_prices_nothing_is_told_and_nothing_sent() -> None:
    said = one(E1, E1_ROW, books.bing())

    assert said.recorded is not None
    (left,) = said.recorded.left_out
    assert left.why is LeftOut.QUOTE_CANNOT_PRICE
    assert "the ledger does not price trades in EUR" in said.reply
    nothing_paid_apart(said)


def test_e8_a_ledger_naming_no_money_ko_is_priced_in_leaves_it_as_before() -> None:
    said = one(E1, E1_ROW, books.ding())

    (card,) = sent(said)
    # As before: the two moneys said apart, no money chosen, the three amounts in doubt.
    assert (card.quote, card.total, card.price) == (None, None, Decimal("69.5"))
    assert mark_on(card, "totalValue") is not None
    nothing_paid_apart(said)


def test_e9_a_share_price_in_usdt_is_never_taken_as_dollars() -> None:
    said = one(
        "今天15:30花了128欧元买了2股KO，一股69.5 USDT",
        KO | {"price": "69.5 USDT", "total": "128欧元"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.total, card.price) == (None, None, Decimal("69.5"))
    nothing_paid_apart(said)


# --- E10 to E13b: sells, coins, the pair that is not taken, and the two guards ----------


def test_e10_a_sell_for_euros_is_sent_with_its_rate() -> None:
    # The fake ledger keeps one pool for each asset and money, so KO bought for euros
    # is there to sell; that buy's rate is the reference.
    bought = books.bought("KO", "EUR", (2026, 11, 1, 16, 0), "60", rate="1.0859")
    trades = (*books.JIA_TRADES, ("t-ko-eur-1", bought), ("t-ko-eur-2", bought))
    said = one(
        "今天15:30卖了2股KO，收到130欧元，一股70美元，手续费0",
        KO | {"side": "sell", "price": "70美元", "total": "130欧元", "fee": "0"},
        books.jia(trades),
    )

    (card,) = sent(said)
    assert (card.quote, card.price, card.total) == ("EUR", Decimal(65), Decimal(130))
    assert card.cost_rate == Decimal("1.0769230769")
    assert "is far from" not in said.reply


def test_e11_a_coin_bought_for_euros_with_no_earlier_such_trade_says_it_was_not_compared() -> None:
    said = one(
        "今天上午10点花了95欧元买了0.001个BTC，价格98000 USDT，手续费0",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "0.001个BTC",
            "price": "98000 USDT",
            "total": "95欧元",
            "fee": "0",
            "time": "今天上午10点",
        },
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.price, card.total) == ("EUR", Decimal(95000), Decimal(95))
    assert card.cost_rate == Decimal("1.0315789474")
    assert NO_REFERENCE in said.reply and NO_FX_FEE in said.reply


def test_e12_dollars_for_a_coin_priced_in_usdt_go_on_as_before() -> None:
    said = one(
        "今天上午10点花了100美元买了0.001个BTC，价格98000 USDT，手续费0",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "0.001个BTC",
            "price": "98000 USDT",
            "total": "100美元",
            "fee": "0",
            "time": "今天上午10点",
        },
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.total) == (None, None)
    nothing_paid_apart(said)


def test_e13_a_share_price_said_ten_times_too_low_marks_the_rate_suspicious_once() -> None:
    said = one(
        "今天15:30花了128欧元买了2股KO，一股6.95美元，手续费0",
        KO | {"price": "6.95美元", "total": "128欧元", "fee": "0"},
        books.jia(),
    )

    (card,) = sent(said)
    assert card.cost_rate == Decimal("0.10859375")
    marks = [mark for mark in card.marks if mark.field == "costRate"]
    assert len(marks) == 1
    assert marks[0].kind == MarkKind.SUSPICIOUS.value
    reason = marks[0].reason or ""
    assert "6.95 USD" in reason and "70 USD" in reason and "1.0859" in reason


def test_e13b_a_total_said_ten_times_too_low_marks_the_rate_far_from_the_last_one() -> None:
    said = one(
        "今天15:30花了12.8欧元买了2股KO，一股69.5美元，手续费0",
        KO | {"price": "69.5美元", "total": "12.8欧元", "fee": "0"},
        books.jia(),
    )

    (card,) = sent(said)
    assert card.cost_rate == Decimal("10.859375")
    kind, reason = mark_on(card, "costRate") or ("", "")
    assert kind == MarkKind.SUSPICIOUS.value
    assert reason is not None and "10.859375" in reason and "1.0859" in reason
    assert "market price" not in reason


# --- E14 to E17b: what is missing is asked -----------------------------------------------


def test_e14_no_quantity_is_asked_never_worked_out_and_then_sent() -> None:
    ledger = books.jia()
    first, then = talk(
        "今天15:30花了128欧元买了KO，一股69.5美元，手续费0",
        "2",
        rows=[
            {
                "side": "buy",
                "coin": "KO",
                "price": "69.5美元",
                "total": "128欧元",
                "fee": "0",
                "time": "今天15:30",
            }
        ],
        ledger=ledger,
        answers=[copied("2")],
    )

    asked(first, "[Trade 1 of 1: quantity]")
    assert first.recorded is not None
    assert first.recorded.progress.trades[0].draft.quantity is None
    (card,) = sent(then)
    like_e1(card, fee="0")


def test_e15_a_total_with_no_money_is_asked_never_worked_out_then_kept_in_doubt() -> None:
    first, then = talk(
        "今天15:30用欧元买了2股KO，一股69.5美元，手续费0",
        "128欧元",
        rows=[KO | {"price": "69.5美元", "price_currency": "欧元", "fee": "0"}],
        ledger=books.jia(),
        answers=[copied("128欧元")],
    )

    asked(first, "[Trade 1 of 1: total]")
    assert first.recorded is not None
    state = first.recorded.progress.trades[0]
    assert state.draft.total is None and state.record is None and state.card is None
    # Answered, the trade goes on as before, not this way: its three amounts in doubt.
    (card,) = sent(then)
    assert card.total is None and card.cost_rate is None
    nothing_paid_apart(then)


def test_e16_no_share_price_asks_it_in_dollars_and_the_answer_sends_it() -> None:
    first, then = talk(E16, "69.5", rows=[E16_ROW], ledger=books.jia())

    asked(first, "[Trade 1 of 1: price in USD]")
    assert "How much was one share in USD?" in first.reply
    (card,) = sent(then)
    like_e1(card)


def test_e16b_meijin_answered_is_asked_again_saying_what_was_said() -> None:
    first, then = talk(E16, "69.5美金", rows=[E16_ROW], ledger=books.jia())

    asked(first, "[Trade 1 of 1: price in USD]")
    assert then.recorded is not None and then.recorded.ending is RecordEnding.ASKING
    assert "69.5美金" in then.reply and "in USD?" in then.reply
    assert then.sent is None


def test_e16c_usdt_answered_is_asked_again_never_taken_as_dollars() -> None:
    first, then = talk(E16, "69.5 USDT", rows=[E16_ROW], ledger=books.jia())

    asked(first, "[Trade 1 of 1: price in USD]")
    assert then.recorded is not None and then.recorded.ending is RecordEnding.ASKING
    assert "69.5 USDT" in then.reply and "in USD?" in then.reply
    assert then.sent is None


def test_e17a_the_dollar_price_in_the_price_cell_sends_it_the_euro_price_worked_out() -> None:
    said = one(E17, KO | {"price": "69.5美元", "total": "128欧元", "fee": "0.19欧"}, books.jia())

    (card,) = sent(said)
    like_e1(card)


def test_e17b_the_euro_price_in_the_price_cell_asks_the_dollar_price_never_sends_without() -> None:
    ledger = books.jia()
    first, then = talk(
        E17,
        "69.5",
        rows=[KO | {"price": "64欧元", "total": "128欧元", "fee": "0.19欧"}],
        ledger=ledger,
    )

    asked(first, "[Trade 1 of 1: price in USD]")
    assert first.recorded is not None and not first.recorded.trades
    assert ledger.calls.count("propose_add") == 1
    (card,) = sent(then)
    like_e1(card)


# --- E18 to E25: the fee, words that are not a euro, and two trades in one -------------


def test_e18_no_fee_said_is_left_empty_and_the_rate_worked_out_all_the_same() -> None:
    said = one(
        "今天15:30花了128欧元买了2股KO，一股69.5美元",
        KO | {"price": "69.5美元", "total": "128欧元"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.fee, card.fee_asset) == (None, None)
    assert (card.quote, card.price, card.cost_rate) == ("EUR", Decimal(64), Decimal("1.0859375"))


def test_e19_an_fx_fee_in_dollars_stays_in_dollars() -> None:
    said = one(
        "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.2美元",
        KO | {"price": "69.5美元", "total": "128欧元", "fee": "0.2美元"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.fee, card.fee_asset, card.quote) == (Decimal("0.2"), "USD", "EUR")
    assert card.cost_rate == Decimal("1.0859375")


def test_e20_ouyi_is_a_platform_never_a_euro() -> None:
    said = one(
        "今天上午10点在欧易买了0.5个ETH，价格2400 USDT，手续费0",
        {
            "side": "buy",
            "coin": "ETH",
            "quantity": "0.5个ETH",
            "price": "2400 USDT",
            "fee": "0",
            "platform": "欧易",
            "time": "今天上午10点",
        },
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.total, card.platform) == ("USDT", Decimal(1200), "欧易")
    nothing_paid_apart(said)


def test_e21_a_total_with_no_money_is_not_paid_in_the_fees_money() -> None:
    said = one(
        "今天15:30花了128，买了2股KO，一股69.5美元，换汇费0.19欧元",
        KO | {"price": "69.5美元", "total": "128", "fee": "0.19欧元"},
        books.jia(),
    )

    (card,) = sent(said)
    # As before: priced in the dollars the price names, the three amounts in doubt.
    assert (card.quote, card.total) == ("USD", None)
    nothing_paid_apart(said)


def test_e22_a_share_price_with_no_money_is_not_guessed_to_be_either() -> None:
    said = one(
        "今天15:30花了128欧元买了2股KO，一股69.5，换汇费0.19欧元",
        KO | {"price": "69.5", "total": "128欧元", "fee": "0.19欧元"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.total, card.price) == ("EUR", None, Decimal("69.5"))
    nothing_paid_apart(said)


def _two(first: dict[str, str], second: dict[str, str], said: str) -> tuple[TradeCard, ...]:
    (result,) = talk(said, rows=[first, second], ledger=books.jia())
    return sent(result)


def test_e23_a_euro_trade_then_a_dollar_trade_each_keep_their_own_money() -> None:
    euro, dollar = _two(
        E1_ROW,
        PEP | {"time": "今天15:30"},
        "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元；又花了160美元买了1股PEP，手续费0",
    )

    like_e1(euro)
    assert (dollar.quote, dollar.price, dollar.cost_rate) == ("USD", Decimal(160), None)


def test_e24_a_dollar_trade_then_a_euro_trade_each_keep_their_own_money() -> None:
    dollar, euro = _two(
        PEP | {"time": "今天15:30"},
        E1_ROW,
        "今天15:30花了160美元买了1股PEP，手续费0；又花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元",
    )

    like_e1(euro)
    assert (dollar.quote, dollar.price, dollar.cost_rate) == ("USD", Decimal(160), None)


def test_e25_yuan_for_a_share_priced_in_dollars_is_sent_the_same_way() -> None:
    said = one(
        "今天15:30花了1000人民币买了1股KO，一股140美元，手续费0",
        KO | {"quantity": "1股", "price": "140美元", "total": "1000人民币", "fee": "0"},
        books.jia(),
    )

    (card,) = sent(said)
    assert (card.quote, card.price, card.total) == ("CNY", Decimal(1000), Decimal(1000))
    assert card.cost_rate == Decimal("0.14")
    assert NO_REFERENCE in said.reply and NO_FX_FEE in said.reply
