"""The hard lines of trades paid in another money, over every line of the table of examples.

- Every trade sent: its price and total are in the money it was paid in,
  quantity times price is its total within 0.01, and a rate goes only
  with a money paid that is not the asset's own.
- No amount is ever worked out from figures said in two moneys: where
  the price and the total name two moneys and one amount is not said,
  nothing holds a worked-out amount, and the blank one is asked.
- The words: no line says a guess where no money was guessed, and no line
  speaks of an FX fee for a trade that did not go this way.

Every sentence and number is invented; the ledgers are made in
``paid_apart_books``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ledger_hand.core.ledger_limits import TOTAL_TOLERANCE
from ledger_hand.flows.conversation import Said
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from tests.flows import paid_apart_books as books
from tests.flows.test_paid_apart_examples import (
    E1,
    E1_ROW,
    E3,
    E3_ROW,
    E16,
    E16_ROW,
    E17,
    GUESS,
    KO,
    NO_FX_FEE,
    PEP,
    talk,
)

type Book = Callable[[], FakeLedger]

BTC = {"side": "buy", "coin": "BTC", "quantity": "0.001个BTC", "time": "今天上午10点"}
# Each line of the table that sends a trade: (name, ledger, what was said, rows, answers).
SENT: list[tuple[str, Book, tuple[str, ...], list[dict[str, str]]]] = [
    ("E1", books.jia, (E1,), [E1_ROW]),
    (
        "E2",
        books.jia,
        ("今天15:30花了100欧元买了3股KO，一股36.2美元，手续费0",),
        [KO | {"quantity": "3股", "price": "36.2美元", "total": "100欧元", "fee": "0"}],
    ),
    ("E3", books.jia, (E3,), [E3_ROW]),
    (
        "E11",
        books.jia,
        ("今天上午10点花了95欧元买了0.001个BTC，价格98000 USDT，手续费0",),
        [BTC | {"price": "98000 USDT", "total": "95欧元", "fee": "0"}],
    ),
    (
        "E13",
        books.jia,
        ("今天15:30花了128欧元买了2股KO，一股6.95美元，手续费0",),
        [KO | {"price": "6.95美元", "total": "128欧元", "fee": "0"}],
    ),
    (
        "E13b",
        books.jia,
        ("今天15:30花了12.8欧元买了2股KO，一股69.5美元，手续费0",),
        [KO | {"price": "69.5美元", "total": "12.8欧元", "fee": "0"}],
    ),
    ("E16", books.jia, (E16, "69.5"), [E16_ROW]),
    ("E17a", books.jia, (E17,), [KO | {"price": "69.5美元", "total": "128欧元", "fee": "0.19欧"}]),
    (
        "E17b",
        books.jia,
        (E17, "69.5"),
        [KO | {"price": "64欧元", "total": "128欧元", "fee": "0.19欧"}],
    ),
    (
        "E18",
        books.jia,
        ("今天15:30花了128欧元买了2股KO，一股69.5美元",),
        [KO | {"price": "69.5美元", "total": "128欧元"}],
    ),
    (
        "E19",
        books.jia,
        ("今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.2美元",),
        [KO | {"price": "69.5美元", "total": "128欧元", "fee": "0.2美元"}],
    ),
    (
        "E23",
        books.jia,
        (E1 + "；又花了160美元买了1股PEP，手续费0",),
        [E1_ROW, PEP | {"time": "今天15:30"}],
    ),
    (
        "E24",
        books.jia,
        ("今天15:30花了160美元买了1股PEP，手续费0；又" + E1[7:],),
        [PEP | {"time": "今天15:30"}, E1_ROW],
    ),
    (
        "E25",
        books.jia,
        ("今天15:30花了1000人民币买了1股KO，一股140美元，手续费0",),
        [KO | {"quantity": "1股", "price": "140美元", "total": "1000人民币", "fee": "0"}],
    ),
]
OWN_MONEY = {"KO": "USD", "PEP": "USD", "AAPL": "USD", "BTC": "USDT", "ETH": "USDT"}


def _last(book: Book, said: tuple[str, ...], rows: list[dict[str, str]]) -> Said:
    return talk(*said, rows=rows, ledger=book())[-1]


@pytest.mark.parametrize(("name", "book", "said", "rows"), SENT, ids=[line[0] for line in SENT])
def test_every_trade_sent_is_in_the_money_paid_and_carries_a_rate_only_across_moneys(
    name: str, book: Book, said: tuple[str, ...], rows: list[dict[str, str]]
) -> None:
    result = _last(book, said, rows)

    assert result.recorded is not None and result.recorded.ending is RecordEnding.SENT, name
    for card in result.recorded.trades:
        assert card.quote is not None and card.price is not None and card.total is not None
        assert card.quantity is not None
        # One money for the price and the total: the money paid, the card's own.
        assert abs(card.quantity * card.price - card.total) <= TOTAL_TOLERANCE
        across = card.quote != OWN_MONEY[card.asset]
        assert (card.cost_rate is not None) is across, name
    for state, marked in zip(
        (result.recorded.progress.trades[number - 1] for number in result.recorded.numbers),
        result.recorded.marked,
        strict=True,
    ):
        record = state.record or state.card
        assert record is not None
        said_price = record.said_price
        if said_price is None:
            continue
        # The price said in the asset's own money is in none of the four cells.
        figures = {record.quantity, record.price, record.total, record.fee}
        assert said_price.amount not in figures, name
        assert marked.rate is not None and marked.rate.said == said_price


# Price and total named in two moneys, one amount not said: (name, ledger, said, row, label).
ACROSS: list[tuple[str, Book, str, dict[str, str], str]] = [
    (
        "E14",
        books.jia,
        "今天15:30花了128欧元买了KO，一股69.5美元，手续费0",
        {"side": "buy", "coin": "KO", "price": "69.5美元", "total": "128欧元", "fee": "0"},
        "[Trade 1 of 1: quantity]",
    ),
    (
        "E14 with no money KO is priced in",
        books.ding,
        "今天15:30花了128欧元买了KO，一股69.5美元，手续费0",
        {"side": "buy", "coin": "KO", "price": "69.5美元", "total": "128欧元", "fee": "0"},
        "[Trade 1 of 1: quantity]",
    ),
    (
        "E9 with no quantity",
        books.jia,
        "今天15:30花了128欧元买了KO，一股69.5 USDT",
        {"side": "buy", "coin": "KO", "price": "69.5 USDT", "total": "128欧元"},
        "[Trade 1 of 1: quantity]",
    ),
    (
        "E12 with no quantity",
        books.jia,
        "今天上午10点花了100美元买了BTC，价格98000 USDT，手续费0",
        {"side": "buy", "coin": "BTC", "price": "98000 USDT", "total": "100美元", "fee": "0"},
        "[Trade 1 of 1: quantity]",
    ),
    (
        "E15",
        books.jia,
        "今天15:30用欧元买了2股KO，一股69.5美元，手续费0",
        KO | {"price": "69.5美元", "price_currency": "欧元", "fee": "0"},
        "[Trade 1 of 1: total]",
    ),
    (
        "E4 with no quantity",
        books.jia,
        "今天15:30花了210欧元买了AAPL，一股230美金，换汇费0.3欧元",
        {"side": "buy", "coin": "AAPL", "price": "230美金", "total": "210欧元", "fee": "0.3欧元"},
        "[Trade 1 of 1: quantity]",
    ),
]


@pytest.mark.parametrize(
    ("name", "book", "said", "cells", "label"), ACROSS, ids=[line[0] for line in ACROSS]
)
def test_no_amount_is_worked_out_from_figures_said_in_two_moneys(
    name: str, book: Book, said: str, cells: dict[str, str], label: str
) -> None:
    ledger = book()
    (result,) = talk(said, rows=[{"time": "今天15:30"} | cells], ledger=ledger)

    assert result.recorded is not None
    assert result.recorded.ending is RecordEnding.ASKING, (name, result.reply)
    assert result.reply.startswith(label), (name, result.reply)
    for state in result.recorded.progress.trades:
        assert state.record is None and state.card is None
        assert state.draft.derived == frozenset()
    assert "propose_add" not in ledger.calls


NOT_GUESSED = ["E2", "E11", "E13", "E13b", "E16", "E17a", "E17b", "E18", "E19", "E23", "E24", "E25"]


@pytest.mark.parametrize("name", ["E1", *NOT_GUESSED])
def test_no_trade_whose_money_was_named_says_it_is_a_guess(name: str) -> None:
    (_, book, said, rows) = next(line for line in SENT if line[0] == name)
    result = _last(book, said, rows)

    assert GUESS not in result.reply
    assert NO_FX_FEE in result.reply


# Lines of the table that do not go this way, said once each: (name, ledger, said, row).
NOT_THIS_WAY: list[tuple[str, Book, str, dict[str, str]]] = [
    ("E4", books.jia, "今天15:30花了210欧元买了1股AAPL，一股230美金，换汇费0.3欧元",
     {"side": "buy", "coin": "AAPL", "quantity": "1股", "price": "230美金", "total": "210欧元",
      "fee": "0.3欧元", "time": "今天15:30"}),
    ("E5", books.jia, "今天15:30花了150欧元买了1股PEP，一股160美金，手续费0",
     PEP | {"price": "160美金", "total": "150欧元", "time": "今天15:30"}),
    ("E6", books.yi, E1, E1_ROW),
    ("E7", books.bing, E1, E1_ROW),
    ("E8", books.ding, E1, E1_ROW),
    ("E9", books.jia, "今天15:30花了128欧元买了2股KO，一股69.5 USDT",
     KO | {"price": "69.5 USDT", "total": "128欧元"}),
    ("E12", books.jia, "今天上午10点花了100美元买了0.001个BTC，价格98000 USDT，手续费0",
     BTC | {"price": "98000 USDT", "total": "100美元", "fee": "0"}),
    ("E20", books.jia, "今天上午10点在欧易买了0.5个ETH，价格2400 USDT，手续费0",
     {"side": "buy", "coin": "ETH", "quantity": "0.5个ETH", "price": "2400 USDT", "fee": "0",
      "platform": "欧易", "time": "今天上午10点"}),
    ("E21", books.jia, "今天15:30花了128，买了2股KO，一股69.5美元，换汇费0.19欧元",
     KO | {"price": "69.5美元", "total": "128", "fee": "0.19欧元"}),
    ("E22", books.jia, "今天15:30花了128欧元买了2股KO，一股69.5，换汇费0.19欧元",
     KO | {"price": "69.5", "total": "128欧元", "fee": "0.19欧元"}),
]  # fmt: skip


@pytest.mark.parametrize(
    ("name", "book", "said", "cells"), NOT_THIS_WAY, ids=[line[0] for line in NOT_THIS_WAY]
)
def test_a_trade_that_does_not_go_this_way_says_nothing_of_an_fx_fee_or_a_rate(
    name: str, book: Book, said: str, cells: dict[str, str]
) -> None:
    (result,) = talk(said, rows=[cells], ledger=book())

    assert NO_FX_FEE not in result.reply, name
    assert "(USD for 1" not in result.reply and "(USDT for 1" not in result.reply
    assert result.recorded is not None
    assert all(card.cost_rate is None for card in result.recorded.trades)
