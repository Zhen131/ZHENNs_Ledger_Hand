"""Tests of ``scripts/try_assistant.py`` asking the ledger: the table, and who wrote the words."""

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


def test_a_summary_prints_its_header_and_rows_and_the_models_words() -> None:
    status, lines = run(
        ["我10月一共买了多少钱的币？"],
        ScriptedModel(
            [asks("get_period_summary", period="10月", asset="币"), "10月你买入了 874.808 USDT。"]
        ),
    )

    assert status == 0
    start = lines.index("    table:")
    assert lines[start + 1 : start + 5] == [
        "      Time: 2026-10-01 to 2026-10-31",
        "      Asset: all assets",
        "      Not narrowed to '币': it names no asset.",
        "      Trades in this time: 5",
    ]
    assert (
        "      USDT | spent on buys 874.808 | received from sells 920.32 | "
        "realized 99.25813637 USDT" in lines
    )
    assert lines[-3:] == [
        "words by: the model",
        "assistant: 10月你买入了 874.808 USDT。",
        "ending: answered",
    ]


def test_words_withheld_are_marked_as_the_programs_with_the_reason() -> None:
    _, lines = run(
        ["10月6号那天我都做了什么交易"],
        ScriptedModel([asks("list_trades", period="10月6号"), "你买了 0.0083 BTC"]),
    )

    assert "      Time: 2026-10-06" in lines
    assert any(line.startswith("      2026-10-06 11:48 | buy | BTC | 0.0082 |") for line in lines)
    assert lines[-3] == (
        "words by: the program (the model's words were withheld: "
        "0.0083 is not in what the ledger returned)"
    )
    assert lines[-2] == "assistant: Here is what the ledger returned."


def test_the_programs_own_answer_is_printed_as_the_programs() -> None:
    status, lines = run(["12月我买了什么"], ScriptedModel([asks("list_trades", period="12月")]))

    assert status == 0
    assert lines[-3] == "words by: the program"
    assert "'12月' can mean more than one stretch of time" in lines[-2]
    assert lines[-1] == "ending: answered_by_program"
