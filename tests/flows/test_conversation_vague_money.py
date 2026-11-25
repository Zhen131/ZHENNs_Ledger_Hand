"""Tests of vague words for money ("美金", "刀", "$", "bucks") said to the assistant.

The product owner's rule of 2026-11-25: a vague word follows the money
the same trade names outright on its own price, total or fee; otherwise
it is the money of the asset's last trade in the ledger, marked as a
guess; otherwise the user is asked. USDT and the US dollar never stand
for each other, and other moneys count only when the ledger has them.

One test for each line of the table of examples the rule was settled
with, numbered as there; the ledgers are made in ``vague_money_books``.
A scripted model stands in for every call. Every sentence, reply and
number is invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.trade import Inferred, InferredFrom, TradeRecord
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.flows.recording import start
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.flows.scripted_flow import copied, row, screened, table
from tests.flows.vague_money_books import bing, ding, ji, jia, wu, yi

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
GUESS = "This is a guess"
_BUDAPEST = ZoneInfo(INVENTED_ZONE)
ETH_LAST = InferredFrom(
    trade_id="t-eth",
    occurred=datetime(2026, 8, 3, 10, 0, tzinfo=_BUDAPEST),
    money="USDT",
    asset="ETH",
)
MSFT_LAST = InferredFrom(
    trade_id="t-msft",
    occurred=datetime(2026, 8, 5, 16, 0, tzinfo=_BUDAPEST),
    money="USD",
    asset="MSFT",
)
ASKS_QUOTE = "[Trade 1 of 1: pricing currency]"


def talk(
    *said: str,
    rows: Sequence[dict[str, str]],
    ledger: FakeLedger,
    answers: Sequence[Step] = (),
) -> list[Said]:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said[0][:6]))],
        extraction=[table(*rows)],
        answers=answers,
    )
    state = AssistantChat()
    seen = []
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
    (result,) = talk(said, rows=[row(**cells)], ledger=ledger)
    return result


def records(said: Said) -> list[TradeRecord | None]:
    assert said.recorded is not None
    return [state.record for state in said.recorded.progress.trades]


def sent(said: Said) -> tuple[TradeFacts, ...]:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT, said.reply
    return said.recorded.trades


def asked_quote(said: Said, ledger: FakeLedger) -> None:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING, said.reply
    assert said.reply.startswith(ASKS_QUOTE), said.reply
    assert said.sent is None
    assert "propose_add" not in ledger.calls


def not_guessed(record: TradeRecord | None) -> None:
    assert record is not None
    assert record.inferred == frozenset()
    assert record.inferred_from is None


ETH_BUY = {"side": "buy", "coin": "ETH", "quantity": "0.5个ETH", "time": "今天上午10点"}
MSFT_BUY = {"side": "buy", "coin": "MSFT", "quantity": "3股MSFT", "time": "今天15:30"}


# --- the trade names a money outright (rows 1 to 7) ---------------------------------


def test_row_01_usdt_said_is_usdt() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2400 USDT，手续费0",
        ETH_BUY | {"price": "2400 USDT", "fee": "0"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USDT", "USDT")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_02_u_said_is_usdt() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2400U，手续费0",
        ETH_BUY | {"price": "2400U", "fee": "0"},
        jia(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USDT"
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_03_dollars_said_are_usd_with_the_fee() -> None:
    said = one(
        "今天15:30买了3股MSFT，每股400美元，手续费1美元",
        MSFT_BUY | {"price": "400美元", "fee": "1美元"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USD", "USD")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_04_usd_said_is_usd() -> None:
    said = one(
        "今天15:30买了3股MSFT，400 USD一股，手续费0",
        MSFT_BUY | {"price": "400 USD", "fee": "0"},
        jia(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USD"
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_05_meijin_follows_the_usdt_the_price_names() -> None:
    ledger = jia()
    said = one(
        "今天上午10点花了30美金买ETH，成交均价2400 USDT，手续费0",
        {
            "side": "buy",
            "coin": "ETH",
            "total": "30美金",
            "price": "2400 USDT",
            "fee": "0",
            "time": "今天上午10点",
        },
        ledger,
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.total, trade.price) == ("USDT", Decimal(30), Decimal(2400))
    not_guessed(records(said)[0])
    assert GUESS not in said.reply
    assert "list_trades" not in ledger.calls
    assert said.recorded is not None
    assert all(
        issue.kind.name != "UNIT_NOT_THE_PRICE_CURRENCY" for issue in said.recorded.progress.issues
    )


def test_row_06_dao_follows_the_usdt_the_fee_names() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2400刀，手续费0.5 USDT",
        ETH_BUY | {"price": "2400刀", "fee": "0.5 USDT"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USDT", "USDT")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_07_dao_follows_the_dollars_the_fee_names() -> None:
    said = one(
        "今天15:30买了3股MSFT，每股400刀，手续费1美元",
        MSFT_BUY | {"price": "400刀", "fee": "1美元"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USD", "USD")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


# --- the trade names no money: the ledger's last trade (rows 8 to 12) ------------------


def test_row_08_meijin_alone_is_the_usdt_of_eth_s_last_trade_marked_a_guess() -> None:
    ledger = jia()
    said = one(
        "今天上午10点花了30美金买了ETH，均价2400，手续费0",
        {
            "side": "buy",
            "coin": "ETH",
            "total": "30美金",
            "price": "2400",
            "fee": "0",
            "time": "今天上午10点",
        },
        ledger,
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USDT", "USDT")
    record = records(said)[0]
    assert record is not None
    assert record.inferred == frozenset({Inferred.QUOTE})
    assert record.inferred_from == ETH_LAST
    assert (
        "Trade 1: no currency was said, so it is priced in USDT, the currency of the last ETH "
        "trade in the ledger. This is a guess; check it before you confirm."
    ) in said.reply
    assert ledger.calls.count("list_trades") == 1


def test_row_09_dao_for_price_and_fee_is_the_usd_of_msft_s_last_trade_both_guessed() -> None:
    said = one(
        "今天15:30买了3股MSFT，每股400刀，手续费1刀",
        MSFT_BUY | {"price": "400刀", "fee": "1刀"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USD", "USD")
    record = records(said)[0]
    assert record is not None
    assert record.inferred == frozenset({Inferred.QUOTE, Inferred.FEE_COIN})
    assert record.inferred_from == MSFT_LAST
    assert (
        "Trade 1: no currency was said, so it is priced in USD and its fee is taken in USD, the "
        "currency of the last MSFT trade in the ledger. This is a guess; check it before you "
        "confirm."
    ) in said.reply


def test_row_10_btc_takes_the_money_of_its_latest_day() -> None:
    said = one(
        "今天上午10点买了0.01个BTC，价格60000美金，手续费0",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "0.01个BTC",
            "price": "60000美金",
            "fee": "0",
            "time": "今天上午10点",
        },
        jia(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USDT"
    record = records(said)[0]
    assert record is not None and record.inferred_from is not None
    assert record.inferred_from.trade_id == "t-btc-usdt"
    assert GUESS in said.reply


def test_row_11_bucks_is_the_usd_of_msft_s_last_trade() -> None:
    said = one(
        "Bought 3 MSFT shares at 400 bucks each today at 15:30, fee 0",
        {
            "side": "buy",
            "coin": "MSFT",
            "quantity": "3 MSFT shares",
            "price": "400 bucks",
            "fee": "0",
            "time": "today at 15:30",
        },
        jia(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USD"
    record = records(said)[0]
    assert record is not None and record.inferred == frozenset({Inferred.QUOTE})
    assert GUESS in said.reply


def test_row_12_dollar_sign_is_the_usdt_of_eth_s_last_trade() -> None:
    said = one(
        "Bought 0.5 ETH at $2400 today at 10:00, fee 0",
        {
            "side": "buy",
            "coin": "ETH",
            "quantity": "0.5 ETH",
            "price": "$2400",
            "fee": "0",
            "time": "today at 10:00",
        },
        jia(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USDT"
    record = records(said)[0]
    assert record is not None and record.inferred_from == ETH_LAST
    assert GUESS in said.reply


# --- nothing to go by: asked (rows 13 to 19) ---------------------------------------------


def test_row_13_dot_with_no_trade_is_asked_about() -> None:
    ledger = jia()
    said = one(
        "今天上午10点买了2个DOT，价格5美金，手续费0",
        {
            "side": "buy",
            "coin": "DOT",
            "quantity": "2个DOT",
            "price": "5美金",
            "fee": "0",
            "time": "今天上午10点",
        },
        ledger,
    )

    asked_quote(said, ledger)
    assert ledger.calls.count("list_trades") == 1


def test_row_14_pep_with_no_trade_is_asked_about() -> None:
    ledger = jia()
    said = one(
        "今天15:30买了1股PEP，每股$150，手续费0",
        {
            "side": "buy",
            "coin": "PEP",
            "quantity": "1股PEP",
            "price": "$150",
            "fee": "0",
            "time": "今天15:30",
        },
        ledger,
    )

    asked_quote(said, ledger)
    assert ledger.calls.count("list_trades") == 1


def test_row_15_a_ledger_whose_trades_cannot_be_had_is_not_guessed_from() -> None:
    ledger = ding()
    said = one(
        "今天上午10点买了0.5个ETH，价格2400刀，手续费0",
        ETH_BUY | {"price": "2400刀", "fee": "0"},
        ledger,
    )

    asked_quote(said, ledger)
    assert ledger.calls.count("list_trades") == 1


def test_row_16_sol_s_latest_day_used_two_moneys_so_it_is_asked_about() -> None:
    ledger = wu()
    said = one(
        "今天上午10点买了2个SOL，价格150刀，手续费0",
        {
            "side": "buy",
            "coin": "SOL",
            "quantity": "2个SOL",
            "price": "150刀",
            "fee": "0",
            "time": "今天上午10点",
        },
        ledger,
    )

    asked_quote(said, ledger)


def test_row_17_ko_last_bought_for_euros_is_never_guessed_as_euros() -> None:
    ledger = yi()
    said = one(
        "今天15:30买了3股KO，每股60美金，手续费0",
        {
            "side": "buy",
            "coin": "KO",
            "quantity": "3股KO",
            "price": "60美金",
            "fee": "0",
            "time": "今天15:30",
        },
        ledger,
    )

    asked_quote(said, ledger)


def test_row_18_msft_s_dollars_no_longer_pricing_are_never_swapped_for_usdt() -> None:
    ledger = bing()
    said = one(
        "今天15:30买了3股MSFT，每股400美金，手续费0",
        MSFT_BUY | {"price": "400美金", "fee": "0"},
        ledger,
    )

    asked_quote(said, ledger)


def test_row_19_with_usdt_the_one_money_dao_is_still_guessed_and_marked() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2400刀，手续费0",
        ETH_BUY | {"price": "2400刀", "fee": "0"},
        bing(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USDT"
    record = records(said)[0]
    assert record is not None and record.inferred == frozenset({Inferred.QUOTE})
    assert GUESS in said.reply


# --- two trades in one passage (rows 20 to 23b) -------------------------------------------


def test_row_20_the_second_trade_does_not_follow_the_first_trade_s_usdt() -> None:
    said = talk(
        "今天上午10点买了0.5个ETH，价格2400 USDT，手续费0；下午3点买了3股MSFT，每股400刀，手续费0",
        rows=[
            ETH_BUY | {"price": "2400 USDT", "fee": "0"},
            {**MSFT_BUY, "time": "下午3点", "price": "400刀", "fee": "0"},
        ],
        ledger=jia(),
    )[0]

    first, second = sent(said)
    assert (first.quote, second.quote) == ("USDT", "USD")
    eth, msft = records(said)
    not_guessed(eth)
    assert msft is not None and msft.inferred_from == MSFT_LAST
    assert "Trade 2: no currency was said" in said.reply
    assert "Trade 1: no currency was said" not in said.reply


def test_row_21_dollars_copied_into_the_eth_row_s_cell_neither_count_nor_stand_in_the_way() -> None:
    said = talk(
        "下午3点买了3股MSFT，每股400美元，手续费0；4点买了0.5个ETH，价格2400刀，手续费0",
        rows=[
            {**MSFT_BUY, "time": "下午3点", "price": "400美元", "fee": "0"},
            {
                **ETH_BUY,
                "time": "4点",
                "price": "2400刀",
                "fee": "0",
                "price_currency": "美元",
            },
        ],
        ledger=jia(),
    )[0]

    first, second = sent(said)
    assert (first.quote, second.quote) == ("USD", "USDT")
    msft, eth = records(said)
    not_guessed(msft)
    assert eth is not None and eth.inferred_from == ETH_LAST
    assert "Trade 2: no currency was said" in said.reply
    assert "Trade 1: no currency was said" not in said.reply


def test_row_22_usdt_left_in_the_account_does_not_belong_to_the_trade() -> None:
    said = one(
        "账户里还剩500 USDT，今天15:30买了3股MSFT，每股400刀，手续费0",
        MSFT_BUY | {"price": "400刀", "fee": "0", "price_currency": "USDT"},
        jia(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USD"
    record = records(said)[0]
    assert record is not None and record.inferred_from == MSFT_LAST
    assert GUESS in said.reply


def test_row_23_ada_said_with_dao_after_two_trades_named_outright_is_its_own_last_money() -> None:
    said = talk(
        "今天上午10点买了0.5个ETH，价格2400 USDT，手续费0；下午3点买了3股MSFT，每股400美元，"
        "手续费0；4点买了100个ADA，价格0.5刀，手续费0",
        rows=[
            ETH_BUY | {"price": "2400 USDT", "fee": "0"},
            {**MSFT_BUY, "time": "下午3点", "price": "400美元", "fee": "0"},
            {
                "side": "buy",
                "coin": "ADA",
                "quantity": "100个ADA",
                "price": "0.5刀",
                "fee": "0",
                "time": "4点",
            },
        ],
        ledger=jia(),
    )[0]

    trades = sent(said)
    assert [trade.quote for trade in trades] == ["USDT", "USD", "USDT"]
    eth, msft, ada = records(said)
    not_guessed(eth)
    not_guessed(msft)
    assert ada is not None and ada.inferred == frozenset({Inferred.QUOTE})
    assert "Trade 3: no currency was said" in said.reply
    assert "Trade 1: no currency" not in said.reply and "Trade 2: no currency" not in said.reply


def test_row_23a_pep_does_not_follow_the_first_trade_s_usdt() -> None:
    ledger = jia()
    said = talk(
        "今天上午10点买了0.5个ETH，价格2400 USDT，手续费0；下午3点买了1股PEP，每股150刀，手续费0",
        rows=[
            ETH_BUY | {"price": "2400 USDT", "fee": "0"},
            {
                "side": "buy",
                "coin": "PEP",
                "quantity": "1股PEP",
                "price": "150刀",
                "fee": "0",
                "time": "下午3点",
            },
        ],
        ledger=ledger,
    )[0]

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert said.reply.startswith("[Trade 2 of 2: pricing currency]"), said.reply
    eth, pep = records(said)
    not_guessed(eth)
    assert pep is None
    assert "propose_add" not in ledger.calls


def test_row_23b_a_fee_taken_in_a_coin_names_no_money() -> None:
    said = one(
        "今天上午10点花了30美金买了ETH，均价2400，手续费0.0002个ETH",
        {
            "side": "buy",
            "coin": "ETH",
            "total": "30美金",
            "price": "2400",
            "fee": "0.0002个ETH",
            "time": "今天上午10点",
        },
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USDT", "ETH")
    record = records(said)[0]
    assert record is not None and record.inferred == frozenset({Inferred.QUOTE})
    assert GUESS in said.reply


# --- both moneys said (rows 24 to 26) ------------------------------------------------------


def test_row_24_a_price_in_usdt_and_a_fee_in_dollars_are_each_kept() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2400 USDT，手续费1美元",
        ETH_BUY | {"price": "2400 USDT", "fee": "1美元"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USDT", "USD")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_25_a_price_in_usdt_and_a_total_in_dollars_ask_which() -> None:
    ledger = jia()
    said = one(
        "今天上午10点买了0.5个ETH，价格2400 USDT，总共1200美元，手续费0",
        ETH_BUY | {"price": "2400 USDT", "total": "1200美元", "fee": "0"},
        ledger,
    )

    asked_quote(said, ledger)


def test_row_26_dao_beside_both_moneys_said_is_asked_about_not_guessed() -> None:
    ledger = jia()
    said = one(
        "今天上午10点买了0.5个ETH，价格2400U，手续费1美元，总共1200刀",
        ETH_BUY | {"price": "2400U", "fee": "1美元", "total": "1200刀"},
        ledger,
    )

    asked_quote(said, ledger)
    assert "list_trades" not in ledger.calls


# --- other moneys, by the ledger's list (rows 27 to 31) ---------------------------------------


EURO_WORDS = (
    "Trade 1 was not sent: the ledger has no currency EUR yet, so this trade cannot be "
    "recorded. Please add it in the ledger first."
)


def test_row_27_euros_the_ledger_lacks_are_not_sent_and_said_so() -> None:
    ledger = jia()
    said = one(
        "今天上午10点买了0.5个ETH，价格2200欧元，手续费0",
        ETH_BUY | {"price": "2200欧元", "fee": "0"},
        ledger,
    )

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NOTHING_TO_SEND, said.reply
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.MONEY_NOT_IN_LEDGER, "EUR")
    assert EURO_WORDS in said.reply
    assert "no asset" not in said.reply
    assert "propose_add" not in ledger.calls


def test_row_28_ou_is_euros_and_meijin_does_not_follow_them() -> None:
    ledger = jia()
    said = one(
        "今天上午10点花了50欧买了0.12股MSFT，一股400美金，手续费0",
        {
            "side": "buy",
            "coin": "MSFT",
            "quantity": "0.12股MSFT",
            "total": "50欧",
            "price": "400美金",
            "fee": "0",
            "time": "今天上午10点",
        },
        ledger,
    )

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NOTHING_TO_SEND, said.reply
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.MONEY_NOT_IN_LEDGER, "EUR")
    assert EURO_WORDS in said.reply
    assert "propose_add" not in ledger.calls


def test_row_29_euros_the_ledger_prices_in_are_taken() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2200欧元，手续费0",
        ETH_BUY | {"price": "2200欧元", "fee": "0"},
        yi(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("EUR", "EUR")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_30_with_no_dollar_in_the_ledger_dao_is_still_guessed_and_marked() -> None:
    said = one(
        "今天上午10点买了0.5个ETH，价格2400刀，手续费0",
        ETH_BUY | {"price": "2400刀", "fee": "0"},
        ji(),
    )

    (trade,) = sent(said)
    assert trade.quote == "USDT"
    record = records(said)[0]
    assert record is not None and record.inferred == frozenset({Inferred.QUOTE})
    assert GUESS in said.reply


def test_row_31_dollars_said_with_no_dollar_in_the_ledger_are_not_sent() -> None:
    ledger = ji()
    said = one(
        "今天上午10点买了0.5个ETH，价格2400美元，手续费0",
        ETH_BUY | {"price": "2400美元", "fee": "0"},
        ledger,
    )

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NOTHING_TO_SEND, said.reply
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.MONEY_NOT_IN_LEDGER, "USD")
    assert "the ledger has no currency USD yet" in said.reply
    assert "propose_add" not in ledger.calls


# --- English (rows 32 and 33) --------------------------------------------------------------


def test_row_32_dollars_in_english_are_usd() -> None:
    said = one(
        "Bought 3 MSFT shares at 400 dollars each today at 15:30, fee 1 dollar",
        {
            "side": "buy",
            "coin": "MSFT",
            "quantity": "3 MSFT shares",
            "price": "400 dollars",
            "fee": "1 dollar",
            "time": "today at 15:30",
        },
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.fee_asset) == ("USD", "USD")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


def test_row_33_bucks_follow_the_usdt_the_price_names() -> None:
    said = one(
        "Spent 30 bucks on ETH at 2400 USDT today at 10:00, fee 0",
        {
            "side": "buy",
            "coin": "ETH",
            "total": "30 bucks",
            "price": "2400 USDT",
            "fee": "0",
            "time": "today at 10:00",
        },
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.total) == ("USDT", Decimal(30))
    not_guessed(records(said)[0])
    assert GUESS not in said.reply


# --- left as it was (rows 34 and 35) -------------------------------------------------------


def test_row_34_no_word_for_money_is_asked_about_and_the_ledger_is_not_looked_at() -> None:
    ledger = jia()
    said = one(
        "今天上午10点买了0.5个ETH，价格2400，手续费0",
        ETH_BUY | {"price": "2400", "fee": "0"},
        ledger,
    )

    asked_quote(said, ledger)
    assert "list_trades" not in ledger.calls


def test_row_35_the_record_page_s_table_reads_dao_as_usdt_with_nothing_guessed() -> None:
    passage = "今天上午10点买了0.5个ETH，价格2400刀，手续费0"
    model = RoutedModel(
        screen=[screened(("spot_trade", "今天上午10点"))],
        extraction=[table(row(**ETH_BUY, price="2400刀", fee="0"))],
    )

    progress = start(passage, model, now=INVENTED_NOW, zone=INVENTED_ZONE)

    (record,) = progress.records
    assert (record.quote, record.fee_coin) == ("USDT", "USDT")
    not_guessed(record)


# --- answers that carry money (rows 36 to 40) ----------------------------------------------
#
# The table writes these as "花了30 USDT买ETH → 问成交价". With only a total
# said, the program asks the quantity first, so the trade below says its
# quantity, and the model leaves the total out and copies the money into
# the pricing currency's cell: the price is then what is asked.

ETH_ASKED_PRICE = {
    "side": "buy",
    "coin": "ETH",
    "quantity": "0.0125个ETH",
    "fee": "0",
    "time": "今天上午10点",
}
SAID_USDT = "今天上午10点花了30 USDT买了0.0125个ETH，手续费0"
SAID_MEIJIN = "今天上午10点花了30美金买了0.0125个ETH，手续费0"


def test_row_36_dollars_answered_for_a_trade_in_usdt_are_asked_about_with_both_said() -> None:
    first, second = talk(
        SAID_USDT,
        "2400美元",
        rows=[ETH_ASKED_PRICE | {"price_currency": "USDT"}],
        ledger=jia(),
        answers=[copied("2400美元")],
    )

    assert first.reply.startswith("[Trade 1 of 1: price]"), first.reply
    assert second.recorded is not None and second.recorded.ending is RecordEnding.ASKING
    assert second.reply.startswith(ASKS_QUOTE), second.reply
    assert "Before, this trade was priced in USDT; now you said 2400 美元." in second.reply
    (state,) = second.recorded.progress.trades
    assert state.draft.price is None
    assert state.draft.quote == "USDT"


def test_row_36_then_usdt_keeps_usdt_and_asks_the_price_again() -> None:
    *_, third = talk(
        SAID_USDT,
        "2400美元",
        "USDT",
        rows=[ETH_ASKED_PRICE | {"price_currency": "USDT"}],
        ledger=jia(),
        answers=[copied("2400美元")],
    )

    assert third.reply.startswith("[Trade 1 of 1: price]"), third.reply
    assert third.recorded is not None
    (state,) = third.recorded.progress.trades
    assert (state.draft.quote, state.draft.price) == ("USDT", None)


def test_row_37_dao_answered_follows_the_trade_s_usdt() -> None:
    ledger = jia()
    _, second = talk(
        SAID_USDT,
        "2400刀",
        rows=[ETH_ASKED_PRICE | {"price_currency": "USDT"}],
        ledger=ledger,
        answers=[copied("2400刀")],
    )

    (trade,) = sent(second)
    assert (trade.quote, trade.price) == ("USDT", Decimal(2400))
    not_guessed(records(second)[0])
    assert GUESS not in second.reply
    assert "list_trades" not in ledger.calls


def test_row_38_usdt_answered_for_a_guessed_usdt_takes_the_mark_away() -> None:
    first, second = talk(
        SAID_MEIJIN,
        "2400 USDT",
        rows=[ETH_ASKED_PRICE | {"price_currency": "美金"}],
        ledger=jia(),
        answers=[copied("2400 USDT")],
    )

    assert first.reply.startswith("[Trade 1 of 1: price]"), first.reply
    (trade,) = sent(second)
    assert trade.quote == "USDT"
    not_guessed(records(second)[0])
    assert GUESS not in second.reply


def test_row_39_dollars_answered_for_a_guessed_usdt_are_asked_about() -> None:
    _, second = talk(
        SAID_MEIJIN,
        "2400美元",
        rows=[ETH_ASKED_PRICE | {"price_currency": "美金"}],
        ledger=jia(),
        answers=[copied("2400美元")],
    )

    assert second.recorded is not None and second.recorded.ending is RecordEnding.ASKING
    assert second.reply.startswith(ASKS_QUOTE), second.reply
    assert "USDT (a guess from the ledger's last trade)" in second.reply
    assert second.sent is None


def test_row_40_dollars_chosen_make_the_trade_usd_and_take_the_mark_away() -> None:
    *_, third = talk(
        SAID_MEIJIN,
        "2400美元",
        "美元",
        rows=[ETH_ASKED_PRICE | {"price_currency": "美金"}],
        ledger=jia(),
        answers=[copied("2400美元")],
    )

    (trade,) = sent(third)
    assert (trade.quote, trade.price) == ("USD", Decimal(2400))
    not_guessed(records(third)[0])
    assert GUESS not in third.reply


# --- a platform's name (row 41) -------------------------------------------------------------


def test_row_41_ouyi_is_a_platform_not_euros() -> None:
    said = one(
        "今天上午10点在欧易买了0.5个ETH，价格2400 USDT，手续费0",
        ETH_BUY | {"price": "2400 USDT", "fee": "0", "platform": "欧易"},
        jia(),
    )

    (trade,) = sent(said)
    assert (trade.quote, trade.platform) == ("USDT", "欧易")
    not_guessed(records(said)[0])
    assert GUESS not in said.reply
