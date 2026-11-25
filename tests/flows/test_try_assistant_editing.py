"""Tests of ``scripts/try_assistant.py`` changing and deleting: lists, choices, before and after."""

from __future__ import annotations

import io

from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ToolCall, ToolReply
from scripts import try_assistant
from tests.fakes.scripted_model import ScriptedModel, scripted_record


def asks(name: str, **arguments: object) -> ToolReply:
    return ToolReply(
        text="", calls=(ToolCall(name=name, arguments=arguments),), record=scripted_record()
    )


def run(arguments: list[str], model: ScriptedModel) -> tuple[int, list[str]]:
    out = io.StringIO()
    status = try_assistant.main(arguments, out=out, model=model, ledger=FakeLedger(), max_steps=6)
    return status, out.getvalue().splitlines()


def test_a_deletion_saved_prints_the_proposal_and_the_trade_deleted() -> None:
    status, lines = run(
        ["--save", "把9月25号那笔ADA删掉"],
        ScriptedModel([asks("propose_trade_delete", period="9月25号", asset="ADA")]),
    )

    assert status == 0
    assert "sent to the ledger: proposal-1, delete of t-03" in lines
    assert "words by: the program" in lines
    assert "ending: sent" in lines
    assert "trades in the fake ledger: 11 before, 10 after" in lines
    assert any(
        line.startswith("  deleted t-03: 2026-09-25T20:37:00+02:00 buy 640 ADA") for line in lines
    )


def test_two_trades_listed_then_the_second_picked_and_saved_prints_before_and_after() -> None:
    status, lines = run(
        ["--save", "把10月6号那笔的手续费改成0.000009", "第二笔"],
        ScriptedModel(
            [asks("propose_trade_update", period="10月6号", field="fee", new_value="0.000009")]
        ),
    )

    assert status == 0
    assert "2 trades match:" in "\n".join(lines)
    assert any(line.startswith("  2. 2026-10-06 16:25 | buy | ETH") for line in lines)
    assert "ending: picking" in lines
    assert "route: taken as the answer to the question waiting" in lines
    assert "  fee | 0.3669 USDT | 0.000009 USDT  <- changed" in lines
    assert "sent to the ledger: proposal-1, change of t-06" in lines
    changed = [line for line in lines if line.startswith("  changed t-06")]
    assert len(changed) == 2
    assert "fee 0.3669 USDT" in changed[0]
    assert "fee 0.000009 USDT" in changed[1]


def test_a_choice_of_which_amount_follows_is_printed_with_both_ways() -> None:
    status, lines = run(
        ["把10月6号那笔BTC的数量改成0.0081", "总额"],
        ScriptedModel(
            [
                asks(
                    "propose_trade_update",
                    period="10月6号",
                    asset="BTC",
                    field="quantity",
                    new_value="0.0081",
                )
            ]
        ),
    )

    assert status == 0
    text = "\n".join(lines)
    assert "1. the total becomes 501.714 USDT" in text
    assert "2. the price becomes 62704.69135802 USDT" in text
    assert "ending: choosing" in lines
    assert "  total | 507.908 USDT | 501.714 USDT  <- changed" in lines
