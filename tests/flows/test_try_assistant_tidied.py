"""Tests of ``scripts/try_assistant.py``'s two lines: what the words were read as, what is asked.

"read as: ..." comes just before the route, only when tidying changed the
words; words it did not change print exactly what the script printed
before the line was added (taken from the earlier code, from the line
"you said" on). "asked about: ..." comes just before the ending while a
question waits. A scripted model and the fake ledger stand in; every
sentence is invented.
"""

from __future__ import annotations

from ledger_hand.core.followup import AskCell, AskWhichCell, Cell, ConfirmCoin
from ledger_hand.core.validation import Missing, Violation
from ledger_hand.ledger.fake_ledger import FakeLedger
from scripts.try_assistant import asked_about
from tests.fakes.routed_model import RoutedModel
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_try_assistant_recording import RECORD, recording_model, run

ONE_BUY = "今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT"
SAID = "今天上午九点四十分在币安买了0.02 BTC，价格九万四千九百，手续费2 USDT"
TIDIED = "今天上午9点40分在币安买了0.02 BTC，价格94900，手续费2 USDT"

# What the earlier code printed for ONE_BUY with --save, from "you said" on.
PRINTED_BEFORE = """\
you said: 今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT
route: the model chose the tools
step 1: the model asked for 1 tool(s)
  propose_trade_add {}
    handed back: {"status":"sent","message":"The program took this over and has told the user \
where it stands."}
recording: 2 call(s) to the model for this passage so far, apart from the steps
  trade 1: 2026-11-24T09:40:00+01:00 buy 0.02 BTC at 94900 USDT, total 1898 USDT, fee 2 USDT, \
platform 币安, note -
    money: price only money, fee said
    marks: totalValue: computed (worked out as quantity × price)
    price check: within reach of the market price: 64880 USDT on 2026-11-24, about 1.5 times higher
sent to the ledger: proposal-1, 1 trade(s)
words by: the program
assistant: Sent to the ledger. It waits there for you to confirm it on the ledger's own page.
ending: sent

then: --save
proposal-1: pending -> saved
trades in the fake ledger: 11 before, 12 after
  added t-12: 2026-11-24T09:40:00+01:00 buy 0.02 BTC at 94900 USDT, total 1898 USDT, fee 2 USDT, \
platform 币安, note -
"""


def _model(time: str) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[
            table(
                row(
                    side="buy",
                    coin="BTC",
                    quantity="0.02 BTC",
                    price="94900",
                    fee="2 USDT",
                    time=time,
                    platform="币安",
                )
            )
        ],
    )


def test_words_tidied_print_what_they_were_read_as_before_the_route() -> None:
    status, printed = run([SAID], _model("今天上午9点40分"), usdt_only_ledger())

    assert status == 0
    lines = printed.splitlines()
    at = lines.index(f"you said: {SAID}")
    assert lines[at + 1] == f"read as: {TIDIED}"
    assert lines[at + 2] == "route: the model chose the tools"
    assert "sent to the ledger: proposal-1, 1 trade(s)" in lines


def test_words_not_changed_print_what_they_printed_before() -> None:
    status, printed = run(["--save", ONE_BUY], _model("今天上午9:40"), usdt_only_ledger())

    assert status == 0
    assert "read as:" not in printed
    assert printed[printed.index("you said:") :] == PRINTED_BEFORE


def test_a_question_waiting_prints_the_cell_it_asks_about_before_the_ending() -> None:
    status, printed = run(
        ["今天上午9:40在币安买了0.02 BTC，价格94900"], recording_model(), FakeLedger()
    )

    assert status == 0
    lines = printed.splitlines()
    assert lines[-2:] == ["asked about: pricing currency", "ending: asking"]


def test_each_kind_of_question_is_named_in_one_word() -> None:
    assert asked_about(AskCell(Cell.OCCURRED, Missing.OCCURRED)) == "time"
    assert asked_about(AskCell(Cell.FEE, Missing.FEE)) == "fee"
    assert asked_about(ConfirmCoin(Cell.COIN, Missing.COIN_CONFIRMATION)) == "new-coin"
    assert (
        asked_about(AskWhichCell((Cell.QUANTITY, Cell.PRICE), Violation.AMOUNTS_DISAGREE))
        == "which-cell"
    )
