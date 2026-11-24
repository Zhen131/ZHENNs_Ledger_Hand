"""Tests of ``scripts/try_assistant.py`` when the assistant records a trade.

Each thing said prints which way it went and one line saying what reached
the ledger; a trade sent is printed as the proposal holds it; the next
thing said answers a question waiting; ``--save`` and ``--reject`` act on
the proposals still pending and show the book before and after. A scripted
model and the fake ledger stand in; every sentence is invented.
"""

from __future__ import annotations

import io

import pytest

from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ToolCall, ToolReply
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import copied, row, screened, table

NO_FEE = "今天上午9:40在币安买了0.02 BTC，价格94900"
RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)


def recording_model(*tools: object, answers: tuple[str, ...] = ()) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD, *tools],  # type: ignore[list-item]
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[
            table(
                row(
                    side="buy",
                    coin="BTC",
                    quantity="0.02 BTC",
                    price="94900",
                    time="今天上午9:40",
                    platform="币安",
                )
            )
        ],
        answers=list(answers),
    )


def run(arguments: list[str], model: RoutedModel, ledger: FakeLedger) -> tuple[int, str]:
    out = io.StringIO()
    status = try_assistant.main(arguments, out=out, model=model, ledger=ledger, max_steps=6)
    return status, out.getvalue()


def test_a_question_then_its_answer_sends_one_trade_and_save_adds_it() -> None:
    ledger = FakeLedger()

    status, printed = run(
        ["--save", NO_FEE, "手续费 0.1 USDT"],
        recording_model(answers=(copied("0.1 USDT"),)),
        ledger,
    )

    assert status == 0
    lines = printed.splitlines()
    assert "route: the model chose the tools" in lines
    assert "route: taken as the answer to the question waiting" in lines
    assert "assistant: [Trade 1 of 1: fee] What was the fee for this trade?" in lines
    sent = [line for line in lines if line.startswith("sent to the ledger:")]
    assert sent == ["sent to the ledger: nothing", "sent to the ledger: proposal-1, 1 trade(s)"]
    assert (
        "  trade 1: 2026-11-24T09:40:00+01:00 buy 0.02 BTC at 94900 USDT, total 1898 USDT, "
        "fee 0.1 USDT, platform 币安, note -"
    ) in lines
    assert "proposal-1: pending -> saved" in lines
    assert "trades in the fake ledger: 11 before, 12 after" in lines
    assert any(line.startswith("  added t-12: 2026-11-24T09:40:00+01:00 buy") for line in lines)
    assert len(ledger.list_trades(TradeFilter())) == 12


def test_reject_leaves_the_book_as_it_was() -> None:
    ledger = FakeLedger()

    status, printed = run(
        ["--reject", NO_FEE, "手续费 0.1 USDT"],
        recording_model(answers=(copied("0.1 USDT"),)),
        ledger,
    )

    assert status == 0
    assert "proposal-1: pending -> rejected" in printed
    assert "trades in the fake ledger: 11 before, 11 after" in printed
    assert "  added: none" in printed


def test_a_question_left_waiting_ends_well_and_sends_nothing() -> None:
    status, printed = run([NO_FEE], recording_model(), FakeLedger())

    assert status == 0
    assert printed.rstrip().endswith("ending: asking")
    assert "sent to the ledger: nothing" in printed
    assert "recording: asked the model 2 time(s), apart from the steps" in printed


def test_a_takeover_that_finds_no_trade_gives_status_1() -> None:
    wrong = ToolReply(
        text="", calls=(ToolCall(name="place_order", arguments={}),), record=scripted_record()
    )
    model = RoutedModel(tools=[wrong, wrong], screen=[screened()])

    status, printed = run(["你好呀"], model, FakeLedger())

    assert status == 1
    assert "route: the program took over after two wrong steps" in printed
    assert printed.rstrip().endswith("ending: two_missteps, taken over: no_trade")


@pytest.mark.parametrize(
    "options", [["--save", "--reject"], ["--clock", "--clock"], ["--save", "--save"]]
)
def test_an_option_twice_or_both_actions_stop_the_script(options: list[str]) -> None:
    out = io.StringIO()

    assert try_assistant.main([*options, "你好"], out=out) == 2
    assert "give each option once" in out.getvalue()


def test_a_small_figure_is_written_out_in_full() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from ledger_hand.core.ledger_records import TradeFacts
    from ledger_hand.core.trade import Side

    trade = TradeFacts(
        occurred=datetime(2026, 11, 24, 8, 5, tzinfo=UTC),
        side=Side.BUY,
        asset="BTC",
        quantity=Decimal("0.00040811"),
        price=Decimal("61258.60"),
        total=Decimal("25"),
        quote="USDT",
        fee=Decimal("0.0000004"),
        fee_asset="BTC",
        platform="OKX",
        note="",
        raw_text="今早8点05分OKX买入0.00040811BTC",
    )

    line = try_assistant.trade_line(trade)

    assert "fee 0.0000004 BTC" in line
    assert "at 61258.60 USDT" in line
