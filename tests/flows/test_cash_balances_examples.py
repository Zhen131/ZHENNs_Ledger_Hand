"""The examples of cash balances and of money moved said, each said once to the assistant.

Each test is one row of the example table (K1 to K10, S1 to S13): a
sentence said in a new chat, against a ledger made here, a scripted model
standing in for every call. Asked about cash, the program lays out the
ledger's balances as it gave them, nothing added up or converted, or says
truthfully that it cannot; told of a deposit, a withdrawal, an exchange or
a dividend, it says the assistant does not record it and sends nothing;
told of one beside a trade, the trade is recorded and the rest said to be
recorded by hand. Every sentence and figure is invented.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.assistant.outcome import Ending
from ledger_hand.core.cash_words import CashAsk
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.money_asks import Manual
from ledger_hand.flows.cash_answers import (
    BELOW_ZERO_WORDS,
    NO_CASH_ROWS,
    NO_DETAIL_WORDS,
    NOT_RECORDED_EITHER,
    WITHHELD_WORDS,
)
from ledger_hand.flows.cash_question import CASH_WORDS
from ledger_hand.flows.conversation import AssistantChat, Route, Said, WordsBy, say
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind, Message, Role, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.flows.scripted_flow import row, screened, table

YUAN = Asset(
    id="asset-cny", code="CNY", name="Chinese yuan", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
)
EURO = Asset(
    id="asset-eur", code="EUR", name="Euro", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
)
K1_CASH = {"USDT": Decimal("1200.5"), "USD": Decimal("830"), "EUR": Decimal("250")}
K1_ROWS = [
    ("USDT", Decimal("1200.5")),
    ("USD", Decimal("830")),
    ("CNY", Decimal("0")),
    ("EUR", Decimal("250")),
]
PLEASE = "Please record it in the ledger yourself"
THAT_PART = "Please record that part in the ledger yourself"


def k1() -> FakeLedger:
    """USDT 1200.5, USD 830, CNY 0, EUR 250."""
    return FakeLedger(assets=(*INVENTED_ASSETS, YUAN, EURO), cash=K1_CASH)


def no_euro() -> FakeLedger:
    """Cash in USDT and US dollars, no euro in the ledger."""
    return FakeLedger(cash={"USDT": Decimal("1200.5"), "USD": Decimal("830")})


def words(text: str) -> ToolReply:
    return ToolReply(text=text, calls=(), record=scripted_record())


def calls(name: str) -> ToolReply:
    return ToolReply(text="", calls=(ToolCall(name=name, arguments={}),), record=scripted_record())


def said_once(
    text: str,
    ledger: FakeLedger,
    tools: list[Step] = (),  # type: ignore[assignment]
    **scripts: list[Step],
) -> Said:
    model = RoutedModel(tools=tools, **scripts)  # type: ignore[arg-type]
    return say(
        AssistantChat(),
        text,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


def rows(said: Said) -> list[tuple[str, Decimal]]:
    seen = said.cash_seen
    assert seen is not None and seen.shown and seen.balances is not None
    return [(row.code, row.balance) for row in seen.balances.balances]


def assert_balances_said(said: Said, kind: CashAsk) -> None:
    """The program's words on the balances, the model not asked, no figure in the words."""
    assert said.route is Route.CASH
    assert said.cash is kind
    assert said.turn is None and said.recorded is None
    assert said.words_by is WordsBy.PROGRAM
    first = said.reply.splitlines()[0]
    assert first.startswith("These are the cash balances in the ledger, counted up to 2026-11-24.")
    assert "not added together and not converted" in first
    assert not any(character.isdigit() for character in first.replace("2026-11-24", ""))
    assert said.state.chat.items == (
        Message(Role.USER, said.read_as.text if said.read_as else ""),
        Message(Role.ASSISTANT, said.reply),
    )


# --- K: cash balances -----------------------------------------------------------


def test_k1_how_much_usdt_lays_out_every_money_in_order_and_adds_nothing_up() -> None:
    ledger = k1()

    said = said_once("我还有多少USDT", ledger)

    assert_balances_said(said, CashAsk.LEFT)
    assert rows(said) == K1_ROWS
    assert said.reply.count("\n") == 0
    assert "total" not in said.reply.lower() and "合计" not in said.reply
    assert ledger.calls.count("cash_balances") == 1


def test_k2_the_cash_balance_asked_in_english_is_the_same() -> None:
    said = said_once("What is my cash balance?", k1())

    assert_balances_said(said, CashAsk.CASH)
    assert rows(said) == K1_ROWS


def test_k3_a_vague_word_picks_no_row() -> None:
    said = said_once("我还有多少美金", k1())

    assert_balances_said(said, CashAsk.LEFT)
    assert rows(said) == K1_ROWS
    assert said.cash_seen is not None and said.cash_seen.named is None
    assert said.reply.count("\n") == 0


def test_k4_euros_asked_of_a_ledger_without_them_by_the_third_reading() -> None:
    said = said_once("我还有多少欧元", no_euro())

    assert_balances_said(said, CashAsk.LEFT)
    assert rows(said) == [("USDT", Decimal("1200.5")), ("USD", Decimal("830"))]
    assert said.reply.splitlines()[1] == "The ledger has no money EUR."


def test_k4b_eur_asked_of_a_ledger_without_it_by_the_third_reading() -> None:
    said = said_once("我还剩多少EUR", no_euro())

    assert_balances_said(said, CashAsk.LEFT)
    assert said.reply.splitlines()[1] == "The ledger has no money EUR."


def test_k4c_euros_asked_of_a_ledger_with_them_need_no_more_line() -> None:
    said = said_once("我还有多少欧元", k1())

    assert_balances_said(said, CashAsk.LEFT)
    assert rows(said) == K1_ROWS
    assert said.cash_seen is not None and said.cash_seen.named == "EUR"
    assert "no money" not in said.reply


def test_k4d_a_platform_with_euro_in_its_name_is_not_a_money() -> None:
    said = said_once("欧易还有多少币", k1(), tools=[words("你在欧易持有的币要看持仓。")])

    assert said.route is Route.MODEL
    assert said.cash is None


def test_k5_a_balance_below_zero_is_said_not_to_be_a_debt() -> None:
    ledger = FakeLedger(cash={"USDT": Decimal("100"), "USD": Decimal("-30")})

    said = said_once("现金余额是多少", ledger)

    assert_balances_said(said, CashAsk.CASH)
    assert rows(said) == [("USDT", Decimal("100")), ("USD", Decimal("-30"))]
    assert said.reply.splitlines()[1] == BELOW_ZERO_WORDS
    assert "not a debt" in BELOW_ZERO_WORDS


def test_k5b_no_cash_money_at_all_lays_out_no_table() -> None:
    coins_only = tuple(asset for asset in INVENTED_ASSETS if asset.kind is not AssetKind.CASH)
    ledger = FakeLedger(assets=coins_only, trades=(), cash={})

    said = said_once("现金余额是多少", ledger)

    assert said.route is Route.CASH
    assert said.reply == NO_CASH_ROWS
    assert said.cash_seen is not None and not said.cash_seen.shown


def test_k6_a_deposit_asked_gets_no_table() -> None:
    said = said_once("我一共入了多少金", k1())

    assert said.route is Route.CASH
    assert said.cash is CashAsk.DEPOSIT
    assert said.reply == NO_DETAIL_WORDS
    assert said.cash_seen is not None and not said.cash_seen.shown


def test_k7_a_ledger_with_no_tool_says_the_fixed_words_as_before_and_names_no_call() -> None:
    ledger = FakeLedger()

    said = said_once("我还有多少USDT", ledger)

    assert said.reply == CASH_WORDS
    assert said.cash is CashAsk.LEFT
    assert said.cash_seen is not None and said.cash_seen.tool is False
    assert ledger.calls == ["list_assets"]


def test_k7b_euros_asked_of_a_ledger_with_no_tool_say_the_fixed_words() -> None:
    said = said_once("我还有多少欧元", FakeLedger())

    assert said.route is Route.CASH
    assert said.reply == CASH_WORDS


def test_k8_a_ledger_that_cannot_be_asked_gives_no_figure() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "LINK_GONE", "The ledger page is gone.")
    ledger = FakeLedger(failure=failure, cash={"USDT": Decimal("1200.5")})

    said = said_once("我还有多少USDT", ledger)

    assert said.route is Route.CASH
    assert said.reply.startswith("The ledger could not be asked for its cash balances:")
    assert "The ledger page is gone." in said.reply
    assert not any(character.isdigit() for character in said.reply)
    assert said.cash_seen is not None and said.cash_seen.failure is failure


def test_k9_a_coin_still_held_goes_to_the_model_as_before() -> None:
    said = said_once(
        "我现在还有多少BTC", k1(), tools=[calls("get_positions"), words("You hold BTC.")]
    )

    assert said.route is Route.MODEL
    assert said.cash is None
    assert said.turn is not None and said.turn.ending is Ending.ANSWERED


def test_k10_a_figure_unasked_gives_way_to_the_words_for_a_ledger_with_the_tool() -> None:
    said = said_once("帮我看看账户", k1(), tools=[words("你账上还有 50 USDT。")])

    assert said.reply == WITHHELD_WORDS
    assert said.turn is not None and said.turn.withheld is not None
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, WITHHELD_WORDS)
    assert not any(character.isdigit() for character in WITHHELD_WORDS)


def test_k10_with_no_tool_it_gives_way_to_the_fixed_words_as_before() -> None:
    said = said_once("帮我看看账户", FakeLedger(), tools=[words("你账上还有 50 USDT。")])

    assert said.reply == CASH_WORDS


def test_k11_a_table_of_holdings_knows_the_ledger_has_the_tool_once() -> None:
    ledger = k1()

    said = said_once(
        "我现在持有哪些币", ledger, tools=[calls("get_positions"), words("这是你的持仓。")]
    )

    assert said.cash_seen is not None and said.cash_seen.tool is True
    assert ledger.calls.count("cash_balances") == 1


# --- S: money moved said ---------------------------------------------------------


def assert_manual(said: Said, ledger: FakeLedger, kind: Manual) -> None:
    assert said.route is Route.MANUAL
    assert said.manual is not None and said.manual.kinds == (kind,)
    assert said.reply == (
        f"The assistant does not record {kind.value}, so nothing was sent to the ledger. "
        "Please record it in the ledger yourself."
    )
    assert PLEASE in said.reply
    assert said.turn is None and said.recorded is None and said.sent is None
    assert said.words_by is WordsBy.PROGRAM
    assert said.well_ended
    assert "propose_add" not in ledger.calls


def test_s1_a_deposit_said() -> None:
    ledger = k1()
    assert_manual(said_once("我今天入金了500 USDT", ledger), ledger, Manual.DEPOSIT)


def test_s2_a_withdrawal_said() -> None:
    ledger = k1()
    assert_manual(said_once("昨天从币安提现了200U", ledger), ledger, Manual.WITHDRAWAL)


def test_s3_an_exchange_said() -> None:
    ledger = k1()
    assert_manual(said_once("今天把100欧元换成了108美元", ledger), ledger, Manual.EXCHANGE)


def test_s4_a_dividend_said() -> None:
    ledger = k1()
    assert_manual(said_once("可口可乐今天分红了2.1美元", ledger), ledger, Manual.DIVIDEND)


def test_s5_a_deposit_said_in_english() -> None:
    ledger = k1()
    assert_manual(said_once("I deposited 500 USDT today", ledger), ledger, Manual.DEPOSIT)


def test_s6_a_dividend_said_in_english() -> None:
    ledger = k1()
    said = said_once("Got a 2.1 USD dividend from KO today", ledger)
    assert_manual(said, ledger, Manual.DIVIDEND)


def test_s7_an_exchange_said_in_english() -> None:
    ledger = k1()
    assert_manual(said_once("Converted 100 EUR to USD today", ledger), ledger, Manual.EXCHANGE)


def test_s8_put_in_500_dollars_is_said_not_asked() -> None:
    ledger = k1()
    assert_manual(said_once("我入了500美金", ledger), ledger, Manual.DEPOSIT)


S9 = "入金500U，然后今天上午10点买了0.01个BTC，价格98000 USDT，手续费0"
S9_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.01个BTC",
    price="98000 USDT",
    fee="0",
    time="今天上午10点",
)


def test_s9_a_deposit_beside_a_buy_records_the_buy_and_says_the_deposit_is_by_hand() -> None:
    ledger = k1()

    said = said_once(
        S9,
        ledger,
        tools=[calls("propose_trade_add")],
        screen=[screened(("spot_trade", "买了0.01个BTC"))],
        extraction=[table(S9_ROW)],
    )

    assert said.route is Route.MODEL
    assert said.cash is None
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    assert said.sent is not None and said.sent.trades == 1
    (trade,) = said.recorded.trades
    assert (trade.asset, trade.quantity, trade.price, trade.quote) == (
        "BTC",
        Decimal("0.01"),
        Decimal("98000"),
        "USDT",
    )
    assert said.reply.splitlines()[-1] == (
        "You also spoke of deposits: the assistant does not record those. "
        "Please record that part in the ledger yourself."
    )
    assert NOT_RECORDED_EITHER not in said.reply
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, said.reply)


def test_s9b_when_the_model_records_nothing_the_reply_says_the_trade_was_not_recorded() -> None:
    said = said_once(S9, k1(), tools=[words("好的，我知道了。")])

    assert said.route is Route.MODEL
    assert said.recorded is None
    assert THAT_PART in said.reply
    assert "was not recorded either" in said.reply
    assert said.reply.startswith("好的，我知道了。\n")


def test_s9c_a_balance_asked_beside_a_deposit_lays_out_the_table() -> None:
    said = said_once("入金500U，我还有多少USDT", k1())

    assert_balances_said(said, CashAsk.LEFT)
    assert rows(said) == K1_ROWS


def test_s10_a_deposit_asked_of_a_ledger_with_no_tool_says_the_fixed_words() -> None:
    said = said_once("我一共入了多少金", FakeLedger())

    assert said.route is Route.CASH
    assert said.cash is CashAsk.DEPOSIT
    assert said.reply == CASH_WORDS


def test_s11_a_buy_with_an_exchange_fee_is_not_money_moved() -> None:
    said = said_once(
        "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元",
        k1(),
        tools=[words("好的。")],
    )

    assert said.route is Route.MODEL
    assert said.manual is None


def test_s12_usdt_exchanged_for_a_coin_is_a_buy_as_before() -> None:
    said = said_once("今天用100 USDT换了0.001个BTC", k1(), tools=[words("好的。")])

    assert said.route is Route.MODEL
    assert said.manual is None
    assert said.reply == "好的。"


def test_s13_a_request_for_the_deposits_is_no_statement() -> None:
    said = said_once("查一下我的入金", k1())

    assert said.route is Route.CASH
    assert said.cash is CashAsk.DEPOSIT
    assert said.reply == NO_DETAIL_WORDS
