"""Tests of judging one tool call: the four kinds of wrong step, and what is taken.

A tool that is not on the list, an argument the tool does not take, a
required one left out, a choice not on the list, and a copied argument that
is not the user's words are each a wrong step, with a reason. Copied means
word for word, as extraction judges it: case counts, and a number cut in
two is not copied. A blank optional argument counts as not given.
"""

from __future__ import annotations

import pytest

from ledger_hand.assistant.judging import Accepted, Misstep, MisstepKind, judge
from ledger_hand.assistant.tools import ToolName
from ledger_hand.ports import ToolCall

SAID = ("10月6号那天我都做了什么交易",)


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall(name=name, arguments=arguments)


def misstep(verdict: Accepted | Misstep) -> MisstepKind:
    assert isinstance(verdict, Misstep), verdict
    return verdict.kind


def test_a_call_with_copied_words_is_taken() -> None:
    verdict = judge(call("list_trades", period="10月6号", side="buy"), SAID)

    assert verdict == Accepted(
        tool=ToolName.LIST_TRADES, arguments={"period": "10月6号", "side": "buy"}
    )


def test_a_tool_not_on_the_list_is_a_wrong_step() -> None:
    assert misstep(judge(call("place_order"), SAID)) is MisstepKind.UNKNOWN_TOOL


def test_an_argument_the_tool_does_not_take_is_a_wrong_step() -> None:
    assert misstep(judge(call("get_positions", asset="BTC"), SAID)) is MisstepKind.UNKNOWN_ARGUMENT


def test_a_choice_not_on_the_list_is_a_wrong_step() -> None:
    assert misstep(judge(call("list_trades", side="bought"), SAID)) is MisstepKind.NOT_A_CHOICE


def test_a_required_argument_left_out_is_a_wrong_step() -> None:
    verdict = judge(
        call("propose_trade_update", field="fee"), ("把10月6号那笔的手续费改成0.000002",)
    )

    assert misstep(verdict) is MisstepKind.MISSING_ARGUMENT


def test_an_argument_that_is_not_text_is_a_wrong_step() -> None:
    assert misstep(judge(call("list_trades", period=6), SAID)) is MisstepKind.NOT_TEXT


def test_a_date_the_model_wrote_itself_is_not_copied() -> None:
    verdict = judge(call("list_trades", period="2023-10-06"), SAID)

    assert misstep(verdict) is MisstepKind.NOT_COPIED
    assert isinstance(verdict, Misstep)
    assert "not copied from what the user said" in verdict.detail


@pytest.mark.parametrize(
    ("said", "value"),
    [("帮我把那笔BTC的数量改成0.00167", "0.0016"), ("改成 1.2k", "1.2")],
    ids=["half of a number", "a number without its unit"],
)
def test_a_number_cut_in_two_is_not_copied(said: str, value: str) -> None:
    verdict = judge(call("propose_trade_update", field="quantity", new_value=value), (said,))

    assert misstep(verdict) is MisstepKind.NOT_COPIED


def test_case_counts_and_width_does_not() -> None:
    said = ("１０月６号那笔ＢＴＣ",)

    assert isinstance(judge(call("list_trades", period="10月6号", asset="BTC"), said), Accepted)
    assert misstep(judge(call("list_trades", asset="btc"), said)) is MisstepKind.NOT_COPIED


def test_another_name_for_the_asset_is_not_copied() -> None:
    verdict = judge(call("list_trades", asset="BTC"), ("我上个月买了多少比特币",))

    assert misstep(verdict) is MisstepKind.NOT_COPIED


def test_a_blank_optional_argument_counts_as_not_given() -> None:
    verdict = judge(call("list_trades", period="10月6号", asset="", side=""), SAID)

    assert verdict == Accepted(tool=ToolName.LIST_TRADES, arguments={"period": "10月6号"})


def test_words_from_an_earlier_message_of_the_chat_count_as_copied() -> None:
    said = ("10月6号那天我都做了什么交易", "第二笔改成0.000002")

    verdict = judge(
        call("propose_trade_update", trade="第二笔", field="fee", new_value="0.000002"), said
    )

    assert isinstance(verdict, Accepted)
