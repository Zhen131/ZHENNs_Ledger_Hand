"""Tests of ``scripts/try_assistant.py``, with a scripted model and the fake ledger.

``--help`` alone prints the description. With nothing to say, or with the
cloud plug set, the script stops with status 2 before any model is asked.
A turn prints the fixed "now" first, then each step: the tool, its
arguments, what was handed back or why it was a wrong step; then the last
words and the ending. Several sentences make one chat. The status is 0
when every turn was answered, 1 when one was not.
"""

from __future__ import annotations

import io

import pytest

from ledger_hand.ports import ModelError, ModelErrorKind, ToolCall, ToolReply
from ledger_hand.settings import Variable
from scripts import try_assistant
from tests.fakes.scripted_model import ScriptedModel, scripted_record
from tests.flows.scripted_flow import screened


def asks(name: str, **arguments: object) -> ToolReply:
    return ToolReply(
        text="", calls=(ToolCall(name=name, arguments=arguments),), record=scripted_record()
    )


def run(arguments: list[str], model: ScriptedModel) -> tuple[int, str, ScriptedModel]:
    out = io.StringIO()
    status = try_assistant.main(arguments, out=out, model=model, max_steps=6)
    return status, out.getvalue(), model


def test_help_alone_prints_the_description() -> None:
    out = io.StringIO()

    assert try_assistant.main(["--help"], out=out) == 0
    assert "Try the assistant by hand" in out.getvalue()


def test_nothing_to_say_stops_the_script() -> None:
    out = io.StringIO()

    assert try_assistant.main([], out=out) == 2
    assert "nothing to say" in out.getvalue()


def test_the_cloud_plug_stops_the_script_before_any_model_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "cloud")
    out = io.StringIO()

    assert try_assistant.main(["我现在手里有哪些币"], out=out) == 2
    assert Variable.PLUG.value in out.getvalue()


def test_a_turn_prints_the_fixed_now_each_step_and_the_ending() -> None:
    status, printed, _ = run(
        ["我现在手里有哪些币"], ScriptedModel([asks("get_positions"), "You hold four assets."])
    )

    assert status == 0
    lines = printed.splitlines()
    assert lines[0] == (
        "now:    2026-11-24T23:55:00+01:00 in Europe/Budapest (the invented book's moment)"
    )
    assert "you said: 我现在手里有哪些币" in lines
    assert "  get_positions {}" in lines
    handed_back = next(line for line in lines if line.startswith("    handed back:"))
    assert '"asset":"BTC"' in handed_back
    assert lines[-2:] == ["assistant: You hold four assets.", "ending: answered"]


def test_arguments_dropped_unread_are_named() -> None:
    status, printed, _ = run(
        ["Bought 0.02 BTC at 94900"],
        ScriptedModel(
            [
                asks("propose_trade_add", quantity="0.02", price="94900"),
                screened(("open_order", "Bought 0.02 BTC at 94900")),
            ]
        ),
    )

    assert status == 0
    assert "    dropped, unread: quantity, price" in printed
    assert "wrong step" not in printed


def test_a_wrong_step_is_printed_with_why() -> None:
    status, printed, _ = run(
        ["我买了多少比特币"],
        ScriptedModel([asks("list_trades", period="2023-10-06"), "Sorry."]),
    )

    assert status == 0
    assert "    wrong step (not_copied): 'period' is '2023-10-06'" in printed


def test_several_sentences_make_one_chat_and_a_failure_gives_status_1() -> None:
    model = ScriptedModel(
        ["Hello.", ModelError(ModelErrorKind.UNREACHABLE, "the server is not running")]
    )

    status, printed, _ = run(["你好", "我现在手里有哪些币"], model)

    assert status == 1
    assert "failure: ModelError: unreachable: the server is not running" in printed
    assert printed.rstrip().endswith("ending: model_failed")
    assert [item.content for item in model.calls[1].items[1:3]] == [  # type: ignore[union-attr]
        "你好",
        "Hello.",
    ]
