"""Tests of the assistant recording with the asset table the ledger's own list makes.

The ledger's assets are what may be traded, and the money it prices trades
in is what a trade may be priced in: a share bought with US dollars is
recorded priced in USD; a price with no money named is asked about when the
ledger prices in more than one; one money is never taken for another; an
asset or a name the ledger lacks is not sent, with the word the user said.
A scripted model stands in for every call and the fake ledger for the
ledger. Every sentence, reply and trade is invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.trade import Side
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.fakes.usdt_only import USDT_ONLY_ASSETS, usdt_only_ledger
from tests.flows.scripted_flow import copied, row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
EURO = Asset(
    id="asset-eur", code="EUR", name="Euro", kind=AssetKind.CASH, pricing=Pricing.CANNOT_PRICE
)
# The invented book with USD the one money trades are priced in; USDT stays, pricing nothing.
USD_ONLY_ASSETS = tuple(
    Asset(id=one.id, code=one.code, name=one.name, kind=one.kind, pricing=Pricing.CANNOT_PRICE)
    if one.code == "USDT"
    else one
    for one in INVENTED_ASSETS
)

SHARES = "今天15:30在IBKR买了2股MSFT，410美元一股，手续费1美元"
SHARES_ROW = row(
    side="buy",
    coin="MSFT",
    quantity="2股",
    price="410美元",
    fee="1美元",
    time="今天15:30",
    platform="IBKR",
)
ONE_BUY = "今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT"
ONE_BUY_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.02 BTC",
    price="94900",
    fee="2 USDT",
    time="今天上午9:40",
    platform="币安",
)


def talk(
    *said: str,
    rows: Sequence[dict[str, str]],
    ledger: FakeLedger,
    answers: list[Step] = (),  # type: ignore[assignment]
) -> list[Said]:
    evidence = said[0].split("，")[0]
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", evidence))],
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


# --- a share bought with US dollars -----------------------------------------------


def test_a_share_bought_with_dollars_is_one_proposal_priced_in_usd() -> None:
    ledger = FakeLedger()

    (said,) = talk(SHARES, rows=[SHARES_ROW], ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    (trade,) = said.recorded.trades
    assert trade.occurred == datetime(2026, 11, 24, 15, 30, tzinfo=trade.occurred.tzinfo)
    assert (trade.side, trade.asset, trade.quote, trade.fee_asset) == (
        Side.BUY,
        "MSFT",
        "USD",
        "USD",
    )
    assert (trade.quantity, trade.price, trade.total, trade.fee) == (
        Decimal("2"),
        Decimal("410"),
        Decimal("820"),
        Decimal("1"),
    )
    assert trade.platform == "IBKR"
    assert ledger.calls == ["list_assets", "propose_add"]


def test_a_price_with_no_money_is_asked_about_and_the_answer_prices_the_trade() -> None:
    first, second = talk(ONE_BUY, "USDT", rows=[ONE_BUY_ROW], ledger=FakeLedger())

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert first.reply.startswith("[Trade 1 of 1: pricing currency]")
    assert "Answer with one of: USDT, USD." in first.reply
    assert second.recorded is not None and second.recorded.ending is RecordEnding.SENT
    (trade,) = second.recorded.trades
    assert (trade.asset, trade.quote, trade.price, trade.total) == (
        "BTC",
        "USDT",
        Decimal("94900"),
        Decimal("1898"),
    )


def test_with_usdt_the_one_money_a_price_with_no_money_is_sent_without_a_question() -> None:
    (said,) = talk(ONE_BUY, rows=[ONE_BUY_ROW], ledger=usdt_only_ledger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    (trade,) = said.recorded.trades
    assert trade.quote == "USDT"


def test_dao_said_with_two_moneys_to_price_in_asks_which() -> None:
    words = "今天上午9:40花了100刀买了0.001 BTC，手续费0"
    model_row = row(
        side="buy", coin="BTC", quantity="0.001 BTC", total="100刀", fee="0", time="今天上午9:40"
    )

    (said,) = talk(words, rows=[model_row], ledger=FakeLedger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert said.reply.startswith("[Trade 1 of 1: pricing currency]")
    assert said.sent is None


def test_a_price_in_u_and_a_total_in_dollars_ask_which_money() -> None:
    words = "今天上午9:40买了0.01 BTC，价格90000U，总共900美元，手续费0"
    model_row = row(
        side="buy",
        coin="BTC",
        quantity="0.01 BTC",
        price="90000U",
        total="900美元",
        fee="0",
        time="今天上午9:40",
    )

    (said,) = talk(words, rows=[model_row], ledger=FakeLedger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert said.reply.startswith("[Trade 1 of 1: pricing currency]")


def test_a_fee_in_dao_with_two_moneys_asks_what_the_fee_was_paid_in() -> None:
    words = "今天15:30在IBKR买了2股MSFT，410美元一股，手续费1刀"
    model_row = SHARES_ROW | {"fee": "1刀"}

    (said,) = talk(words, rows=[model_row], ledger=FakeLedger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert said.reply.startswith("[Trade 1 of 1: fee coin]")


# --- one money is never taken for another ---------------------------------------------


def test_a_price_in_u_when_only_usd_prices_is_not_sent_and_never_taken_for_usd() -> None:
    words = "今天15:30在IBKR买了2股MSFT，410U一股，手续费1美元"
    model_row = SHARES_ROW | {"price": "410U"}
    ledger = FakeLedger(assets=USD_ONLY_ASSETS)

    (said,) = talk(words, rows=[model_row], ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.QUOTE_CANNOT_PRICE, "USDT")
    assert "Trade 1 was not sent: the ledger does not price trades in USDT." in said.reply
    assert "propose_add" not in ledger.calls


def test_a_price_in_dollars_when_only_usdt_prices_is_not_sent_and_never_taken_for_usdt() -> None:
    ledger = usdt_only_ledger()

    (said,) = talk(SHARES, rows=[SHARES_ROW], ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.QUOTE_CANNOT_PRICE, "USD")
    assert "the ledger does not price trades in USD." in said.reply
    assert "propose_add" not in ledger.calls


def test_a_missing_price_is_asked_in_the_money_the_trade_is_priced_in() -> None:
    words = "今天15:30在IBKR买了2股MSFT，手续费1美元"
    model_row = row(
        side="buy", coin="MSFT", quantity="2股", fee="1美元", time="今天15:30", platform="IBKR"
    )

    first, second, third = talk(
        words, "美元", "410", rows=[model_row], ledger=FakeLedger(), answers=[copied("410")]
    )

    assert first.reply.startswith("[Trade 1 of 1: pricing currency]")
    assert second.reply.startswith("[Trade 1 of 1: price] What was the price of one unit, in USD?")
    assert "USDT" not in second.reply
    assert third.recorded is not None and third.recorded.ending is RecordEnding.SENT
    (trade,) = third.recorded.trades
    assert (trade.quote, trade.price, trade.total) == ("USD", Decimal("410"), Decimal("820"))


# --- what the ledger lacks, and money traded ------------------------------------------


def test_a_coin_known_by_name_but_not_in_the_ledger_is_named_as_said() -> None:
    words = "今天上午9:40买了100狗狗币，价格0.2 USDT，手续费0"
    model_row = row(
        side="buy", coin="狗狗币", quantity="100", price="0.2 USDT", fee="0", time="今天上午9:40"
    )

    (said,) = talk(words, rows=[model_row], ledger=FakeLedger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.NOT_IN_LEDGER, "狗狗币")
    assert "Trade 1 was not sent: the ledger has no asset 狗狗币 yet." in said.reply


def test_a_share_the_ledger_lacks_is_not_sent_and_the_user_is_asked_to_add_it() -> None:
    words = "今天15:30在IBKR买了2股AAPL，230美元一股，手续费1美元"
    model_row = SHARES_ROW | {"coin": "AAPL", "price": "230美元"}

    (said,) = talk(words, rows=[model_row], ledger=FakeLedger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.NOT_IN_LEDGER, "AAPL")
    assert "the ledger has no asset AAPL yet. Please add it in the ledger first." in said.reply


def test_money_the_ledger_prices_nothing_in_bought_as_an_asset_is_an_exchange() -> None:
    words = "今天上午9:40买了100 EUR，价格1.08美元，手续费0"
    model_row = row(
        side="buy", coin="EUR", quantity="100 EUR", price="1.08美元", fee="0", time="今天上午9:40"
    )
    ledger = FakeLedger(assets=(*INVENTED_ASSETS, EURO))

    (said,) = talk(words, rows=[model_row], ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.MONEY_TRADED, "EUR")
    assert "EUR is a currency in the ledger" in said.reply
    assert "no asset" not in said.reply


def test_usdt_bought_with_dollars_is_an_exchange_and_is_not_sent() -> None:
    words = "今天上午9:40用美元买了500 USDT，价格1美元，手续费0"
    model_row = row(
        side="buy", coin="USDT", quantity="500 USDT", price="1美元", fee="0", time="今天上午9:40"
    )

    (said,) = talk(words, rows=[model_row], ledger=FakeLedger())

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.MONEY_TRADED, "USDT")
    assert "does not record an exchange of currencies" in said.reply


def test_money_written_after_a_number_that_the_reader_does_not_know_is_never_usdt_or_usd() -> None:
    words = "今天上午9:40买了0.1 BTC，价格60000欧元，手续费0"
    model_row = row(
        side="buy", coin="BTC", quantity="0.1 BTC", price="60000欧元", fee="0", time="今天上午9:40"
    )
    ledger = FakeLedger(assets=(*USDT_ONLY_ASSETS, EURO))

    (said,) = talk(words, rows=[model_row], ledger=ledger)

    assert said.recorded is not None
    assert said.sent is None
    assert "propose_add" not in ledger.calls
    (state,) = said.recorded.progress.trades
    assert state.record is None


# --- the second guard, against the list asked for when the trade is sent ---------------


class ChangingLedger(FakeLedger):
    """A fake ledger whose list of assets is a different one from the second time on."""

    def __init__(self, first: tuple[Asset, ...], later: tuple[Asset, ...]) -> None:
        super().__init__(assets=first)
        self._lists = [first, later]

    def list_assets(self) -> tuple[Asset, ...]:
        self.calls.append("list_assets")
        return self._lists[0] if len(self._lists) == 1 else self._lists.pop(0)


def test_money_the_ledger_stopped_pricing_in_while_a_question_waited_is_not_sent() -> None:
    words = "今天15:30在IBKR买了2股MSFT，410美元一股"
    model_row = SHARES_ROW | {"fee": ""}
    ledger = ChangingLedger(INVENTED_ASSETS, USDT_ONLY_ASSETS)

    first, second = talk(words, "1美元", rows=[model_row], ledger=ledger, answers=[copied("1美元")])

    assert first.reply.startswith("[Trade 1 of 1: fee]")
    assert second.recorded is not None and second.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = second.recorded.left_out
    assert (left.why, left.code) == (LeftOut.QUOTE_CANNOT_PRICE, "USD")
    assert ledger.calls == ["list_assets", "list_assets"]


def test_a_price_in_u_and_a_total_in_dollars_when_only_usdt_prices_is_not_sent() -> None:
    words = "今天上午9:40买了0.01 BTC，价格90000U，总共900美元，手续费0"
    model_row = row(
        side="buy",
        coin="BTC",
        quantity="0.01 BTC",
        price="90000U",
        total="900美元",
        fee="0",
        time="今天上午9:40",
    )
    ledger = usdt_only_ledger()

    (said,) = talk(words, rows=[model_row], ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = said.recorded.left_out
    assert (left.why, left.code) == (LeftOut.QUOTE_CANNOT_PRICE, "USD")
    assert "propose_add" not in ledger.calls
