"""Tests of judging a call to change or delete a trade."""

from __future__ import annotations

from ledger_hand.assistant.edit_calls import EditCall, WrongParts, judge_edit, wrong_parts
from ledger_hand.assistant.judging import Misstep, MisstepKind
from ledger_hand.assistant.tools import ToolName
from ledger_hand.ports import ToolCall

SAID = ("把10月6号那笔BTC的数量改成0.0081",)


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall(name=name, arguments=arguments)


def test_a_change_in_the_users_words_is_taken_with_the_asset_apart_and_the_trade_dropped() -> None:
    verdict = judge_edit(
        call(
            "propose_trade_update",
            period="10月6号",
            asset="比特币",
            side="buy",
            trade="t-05",
            field="quantity",
            new_value="0.0081",
        ),
        SAID,
    )

    assert verdict == EditCall(
        tool=ToolName.PROPOSE_TRADE_UPDATE,
        period="10月6号",
        asset="比特币",
        side="buy",
        field="quantity",
        new_value="0.0081",
    )


def test_a_trade_that_is_not_text_is_dropped_too() -> None:
    verdict = judge_edit(call("propose_trade_delete", period="10月6号", trade=2), SAID)

    assert verdict == EditCall(tool=ToolName.PROPOSE_TRADE_DELETE, period="10月6号")


def test_a_year_the_model_wrote_is_a_wrong_step() -> None:
    verdict = judge_edit(call("propose_trade_delete", period="2023-10-06"), SAID)

    assert isinstance(verdict, Misstep)
    assert verdict.kind is MisstepKind.NOT_COPIED
    assert verdict.detail.startswith("'period' is ")


def test_an_asset_that_is_not_text_is_a_wrong_step() -> None:
    verdict = judge_edit(call("propose_trade_delete", period="10月6号", asset=5), SAID)

    assert isinstance(verdict, Misstep)
    assert verdict.kind is MisstepKind.NOT_TEXT


def test_a_new_value_cut_from_a_number_is_a_wrong_step() -> None:
    verdict = judge_edit(
        call("propose_trade_update", period="10月6号", field="quantity", new_value="0.008"), SAID
    )

    assert isinstance(verdict, Misstep)


def test_which_parts_of_a_wrong_call_are_wrong() -> None:
    both = call("propose_trade_update", period="2023-10-06", field="quantity", new_value="0.008")
    value = call("propose_trade_update", period="10月6号", field="quantity", new_value="0.008")
    unknown = call("propose_trade_delete", when="10月6号")
    no_field = call("propose_trade_update", period="10月6号", field="amount", new_value="0.008")

    assert wrong_parts(both, SAID) == WrongParts(
        period_wrong=True, field_taken=True, new_value_wrong=True
    )
    assert wrong_parts(value, SAID) == WrongParts(
        period_wrong=False, field_taken=True, new_value_wrong=True
    )
    assert wrong_parts(unknown, SAID) == WrongParts(
        period_wrong=False, field_taken=False, new_value_wrong=False
    )
    assert wrong_parts(no_field, SAID).field_taken is False
