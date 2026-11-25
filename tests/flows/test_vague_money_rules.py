"""Tests that walk the rule for vague words for money through its combinations.

Beside the table of examples (``test_conversation_vague_money``): every
vague word with nothing to go by is asked about; every mix of a money
said outright, a vague word, the asset's last money in the ledger and a
money answered sends only a money the user said, the trade named, the
ledger's last trade gave or the user answered, and asks first when an
answer names another money; the ledger is asked once for an asset; the
Record page's table never guesses; which units count as naming a money
outright; how the last money is found; a guess and its trade go
together. Every number is invented.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.ledger_records import AssetKind
from ledger_hand.core.ledger_table import VAGUE_MONEY_WORDS, table_of
from ledger_hand.core.trade import Inferred, InferredFrom, TradeDraft, TradeRecord
from ledger_hand.extraction.passage import Passage
from ledger_hand.extraction.reply_parser import ReplyRow
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.row_draft import Surroundings, draft_from_row
from ledger_hand.flows.last_money import LastMoney, LastMoneyMiss, last_money_of
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.flows.recording import start
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from tests.flows.scripted_flow import copied, row, screened, table
from tests.flows.test_conversation_vague_money import ETH_BUY, records, talk
from tests.flows.vague_money_books import JIA_ASSETS, JIA_TRADES, asset, bought, jia

_BUDAPEST = ZoneInfo(INVENTED_ZONE)


# --- with nothing to go by, every vague word is asked about ---------------------------------


@pytest.mark.parametrize("word", VAGUE_MONEY_WORDS)
@pytest.mark.parametrize("another", [None, "2400 USDT", "2400美元"])
def test_every_vague_word_with_no_last_trade_is_asked_about_and_nothing_is_sent(
    word: str, another: str | None
) -> None:
    ledger = jia()
    dot = {
        "side": "buy",
        "coin": "DOT",
        "quantity": "2个DOT",
        "price": f"5{word}" if word != "$" else "$5",
        "fee": "0",
        "time": "今天上午10点",
    }
    rows = [dot]
    passage = f"今天上午10点买了2个DOT，价格{dot['price']}，手续费0"
    if another is not None:
        passage = f"今天上午9点买了0.5个ETH，价格{another}，手续费0；" + passage
        rows = [{**ETH_BUY, "time": "今天上午9点", "price": another, "fee": "0"}, dot]

    (said,) = talk(passage, rows=rows, ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING, said.reply
    assert f"of {len(rows)}: pricing currency]" in said.reply.split("\n")[0]
    assert said.sent is None
    assert "propose_add" not in ledger.calls
    assert ledger.calls.count("list_trades") == 1


# --- every mix: only a money said, named, guessed or answered is sent --------------------


PRICE_WORDS = {
    "2400 USDT": "USDT",
    "2400U": "USDT",
    "2400美元": "USD",
    "2400 USD": "USD",
    "2400美金": None,
    "2400刀": None,
    "$2400": None,
}
FEE_WORDS = {"0": "zero", "0.5 USDT": "USDT", "1美元": "USD", "1刀": None}
LAST = ("USDT", "USD", None)


def _ledger_with_eth_last(money: str | None) -> FakeLedger:
    trades = tuple(pair for pair in JIA_TRADES if pair[1].asset != "ETH")
    if money is not None:
        trades = (*trades, ("t-eth", bought("ETH", money, (2026, 8, 3, 10, 0))))
    return FakeLedger(assets=JIA_ASSETS, trades=trades)


def _expected(price: str | None, fee: str | None, last: str | None) -> tuple[str, str] | None:
    """The moneys the rule gives the trade, or ``None`` when it asks; worked out apart."""
    named = {money for money in (price, fee) if money not in (None, "zero")}
    follow = next(iter(named)) if len(named) == 1 else None
    quote = price or follow or last
    if fee == "zero":
        return None if quote is None else (quote, quote)
    fee_money = fee or follow or last
    if quote is None or fee_money is None:
        return None
    return quote, fee_money


@pytest.mark.parametrize("last", LAST)
@pytest.mark.parametrize("fee_words", sorted(FEE_WORDS))
@pytest.mark.parametrize("price_words", sorted(PRICE_WORDS))
def test_every_mix_sends_only_a_money_said_named_or_guessed(
    price_words: str, fee_words: str, last: str | None
) -> None:
    ledger = _ledger_with_eth_last(last)
    passage = f"今天上午10点买了0.5个ETH，价格{price_words}，手续费{fee_words}"

    (said,) = talk(
        passage, rows=[ETH_BUY | {"price": price_words, "fee": fee_words}], ledger=ledger
    )

    expected = _expected(PRICE_WORDS[price_words], FEE_WORDS[fee_words], last)
    assert said.recorded is not None
    if expected is None:
        assert said.recorded.ending is RecordEnding.ASKING, said.reply
        assert "propose_add" not in ledger.calls
        return
    assert said.recorded.ending is RecordEnding.SENT, said.reply
    (trade,) = said.recorded.trades
    assert (trade.quote, trade.fee_asset) == expected
    record = records(said)[0]
    assert record is not None
    guessed = record.inferred != frozenset()
    assert guessed == (GUESS_WORDS in said.reply)
    if guessed:
        assert record.inferred_from is not None and record.inferred_from.money == last


GUESS_WORDS = "This is a guess"


@pytest.mark.parametrize(
    ("trade_money", "answered", "then"),
    [
        ("USDT", "2400 USDT", "filled"),
        ("USDT", "2400U", "filled"),
        ("USDT", "2400刀", "filled"),
        ("USDT", "2400美元", "asked"),
        ("USDT", "2400 USD", "asked"),
        ("美金", "2400 USDT", "filled"),
        ("美金", "2400刀", "filled"),
        ("美金", "2400美元", "asked"),
        ("美元", "2400美元", "filled"),
        ("美元", "2400 USDT", "asked"),
        ("美元", "$2400", "filled"),
    ],
)
def test_an_answer_s_money_never_quietly_replaces_the_trade_s(
    trade_money: str, answered: str, then: str
) -> None:
    ledger = jia()
    passage = f"今天上午10点用{trade_money}买了0.0125个ETH，手续费0"
    cells = {
        "side": "buy",
        "coin": "ETH",
        "quantity": "0.0125个ETH",
        "fee": "0",
        "time": "今天上午10点",
        "price_currency": trade_money,
    }

    first, second = talk(passage, answered, rows=[cells], ledger=ledger, answers=[copied(answered)])

    assert first.reply.startswith("[Trade 1 of 1: price]"), first.reply
    assert second.recorded is not None
    if then == "asked":
        assert second.recorded.ending is RecordEnding.ASKING
        assert second.reply.startswith("[Trade 1 of 1: pricing currency]"), second.reply
        assert "now you said" in second.reply
        return
    (trade,) = second.recorded.trades
    before = {"USDT": "USDT", "美金": "USDT", "美元": "USD"}[trade_money]
    assert (trade.quote, trade.price) == (before, Decimal(2400))


def test_a_fee_answered_in_another_money_is_asked_about() -> None:
    passage = "今天上午10点买了0.5个ETH，价格2400 USDT，手续费"
    cells = ETH_BUY | {"price": "2400 USDT", "fee_currency": "USDT"}

    first, second = talk(passage, "1美元", rows=[cells], ledger=jia(), answers=[copied("1美元")])

    assert first.reply.startswith("[Trade 1 of 1: fee]"), first.reply
    assert second.reply.startswith("[Trade 1 of 1: fee asset]"), second.reply
    assert "Before, its fee was taken in USDT; now you said 1 美元." in second.reply


# --- the ledger is asked once for an asset ----------------------------------------------------


def test_two_trades_of_one_asset_ask_the_ledger_once() -> None:
    ledger = jia()
    passage = (
        "今天上午9点买了0.5个ETH，价格2400刀，手续费0；上午10点买了0.5个ETH，价格2500刀，手续费0"
    )
    rows = [
        {**ETH_BUY, "time": "今天上午9点", "price": "2400刀", "fee": "0"},
        {**ETH_BUY, "time": "上午10点", "price": "2500刀", "fee": "0"},
    ]

    (said,) = talk(passage, rows=rows, ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT, said.reply
    assert [trade.quote for trade in said.recorded.trades] == ["USDT", "USDT"]
    assert ledger.calls.count("list_trades") == 1


# --- the Record page's table never guesses ----------------------------------------------------


@pytest.mark.parametrize("price", ["2400刀", "2400美金", "$2400", "2400 USDT", "2400美元", "2400"])
def test_the_record_page_s_table_never_marks_a_guess(price: str) -> None:
    from tests.fakes.routed_model import RoutedModel

    passage = f"今天上午10点买了0.5个ETH，价格{price}，手续费0"
    model = RoutedModel(
        screen=[screened(("spot_trade", "今天上午10点"))],
        extraction=[table(row(**ETH_BUY, price=price, fee="0"))],
    )

    progress = start(passage, model, now=INVENTED_NOW, zone=INVENTED_ZONE)

    for trade in progress.trades:
        assert trade.draft.inferred == frozenset() and trade.draft.inferred_from is None
        if trade.record is not None:
            assert trade.record.inferred == frozenset() and trade.record.inferred_from is None
    assert progress.last_moneys == ()


# --- which units name a money outright --------------------------------------------------------


def _row_quote(cells: dict[str, str]) -> str | None:
    table_ = table_of(JIA_ASSETS)
    assert table_ is not None
    passage = Passage("，".join(cells.values()))
    reply = ReplyRow(
        side=None,
        cells={Field(name): text for name, text in cells.items()},
    )
    made = draft_from_row(reply, 0, Surroundings(passage, table_, INVENTED_NOW, INVENTED_ZONE))
    return made.draft.quote


@pytest.mark.parametrize(
    ("fee", "quote"),
    [
        ("0.5 USDT", "USDT"),
        ("0.5U", "U"),
        ("1 USD", "USD"),
        ("1美元", "美元"),
        ("1美金", "刀"),
        ("1刀", "刀"),
        ("0.0002个ETH", "刀"),
    ],
)
def test_a_fee_named_outright_is_followed_and_a_vague_or_coin_fee_is_not(
    fee: str, quote: str
) -> None:
    assert _row_quote({"coin": "ETH", "price": "2400刀", "fee": fee}) == quote


@pytest.mark.parametrize(
    ("price", "quote"),
    [
        ("2400 USDT", "USDT"),
        ("2400U", "U"),
        ("400 USD", "USD"),
        ("400美元", "美元"),
        ("400美金", "美金"),
        ("400刀", "刀"),
        ("$400", "$"),
        ("400 bucks", "bucks"),
    ],
)
def test_a_price_names_a_money_outright_only_in_a_word_that_names_one(
    price: str, quote: str
) -> None:
    # A word naming one money is followed by the total's "美金"; a vague one
    # stays, the price's first, to be guessed.
    assert _row_quote({"coin": "ETH", "total": "30美金", "price": price}) == quote


@pytest.mark.parametrize("cell", ["USDT", "美元"])
def test_the_two_currency_cells_never_count_as_named_outright(cell: str) -> None:
    quote = _row_quote({"coin": "ETH", "price": "2400刀", "price_currency": cell})
    fee_cell = _row_quote({"coin": "ETH", "price": "2400刀", "fee_currency": cell})

    assert quote == "刀"
    assert fee_cell == "刀"


# --- how the last money is found --------------------------------------------------------------


def _found(trades: tuple[tuple[str, object], ...], code: str = "ETH") -> LastMoney:
    assets = (*JIA_ASSETS, asset("SOL", AssetKind.CRYPTO))
    ledger = FakeLedger(assets=assets, trades=trades)  # type: ignore[arg-type]
    return last_money_of(ledger, INVENTED_NOW)(code)


def test_the_latest_day_s_money_is_found_with_its_latest_trade() -> None:
    last = _found(
        (
            ("a", bought("ETH", "USD", (2026, 8, 1, 10, 0))),
            ("b", bought("ETH", "USDT", (2026, 8, 2, 9, 0))),
            ("c", bought("ETH", "USDT", (2026, 8, 2, 18, 0))),
        )
    )

    assert last.found == InferredFrom(
        trade_id="c",
        occurred=datetime(2026, 8, 2, 18, 0, tzinfo=_BUDAPEST),
        money="USDT",
        asset="ETH",
    )


def test_two_moneys_on_the_latest_day_find_nothing_whichever_came_first() -> None:
    for first, second in (("USDT", "USD"), ("USD", "USDT")):
        last = _found(
            (
                ("a", bought("ETH", first, (2026, 8, 2, 9, 0))),
                ("b", bought("ETH", second, (2026, 8, 2, 9, 0))),
            )
        )
        assert last == LastMoney(miss=LastMoneyMiss.TWO_MONEYS)


def test_a_trade_after_now_does_not_count() -> None:
    later = INVENTED_NOW + timedelta(days=1)
    when = (later.year, later.month, later.day, 10, 0)
    last = _found(
        (
            ("a", bought("ETH", "USDT", (2026, 8, 2, 9, 0))),
            ("b", bought("ETH", "USD", when)),
        )
    )

    assert last.found is not None and last.found.money == "USDT"


def test_no_trade_finds_nothing() -> None:
    assert _found(()) == LastMoney(miss=LastMoneyMiss.NO_TRADE)


def test_an_asset_the_ledger_does_not_know_finds_nothing() -> None:
    assert _found((), code="XYZ") == LastMoney(miss=LastMoneyMiss.LEDGER_FAILED)


def test_a_last_money_is_found_or_missed_never_both() -> None:
    source = InferredFrom(trade_id="a", occurred=INVENTED_NOW, money="USDT", asset="ETH")
    with pytest.raises(ValueError):
        LastMoney()
    with pytest.raises(ValueError):
        LastMoney(found=source, miss=LastMoneyMiss.NO_TRADE)


# --- a guess and its trade go together --------------------------------------------------------


def test_a_guess_and_the_trade_it_came_from_go_together() -> None:
    source = InferredFrom(trade_id="a", occurred=INVENTED_NOW, money="USDT", asset="ETH")

    with pytest.raises(ValueError):
        TradeDraft(inferred=frozenset({Inferred.QUOTE}))
    with pytest.raises(ValueError):
        TradeDraft(inferred_from=source)
    assert TradeDraft(inferred=frozenset({Inferred.QUOTE}), inferred_from=source).inferred_from
    record = dict(
        side=None,
        coin="ETH",
        quantity=Decimal(1),
        price=Decimal(1),
        total=Decimal(1),
        quote="USDT",
        derived=None,
        fee=Decimal(0),
        fee_coin="USDT",
        occurred=None,
        raw_text="x",
    )
    with pytest.raises(ValueError):
        TradeRecord(**record, inferred=frozenset({Inferred.FEE_COIN}))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        TradeRecord(**record, inferred_from=source)  # type: ignore[arg-type]


def test_the_built_in_table_has_no_vague_word() -> None:
    assert all(BUILT_IN_ASSETS.money(word).reading.name != "VAGUE" for word in VAGUE_MONEY_WORDS)
