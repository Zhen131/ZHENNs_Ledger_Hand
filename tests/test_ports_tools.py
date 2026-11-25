"""Tests of the shapes of a call with tools, and of the ledger port's error.

The shapes refuse what they cannot be: a reply with no call and no text, a
turn with no call, arguments that are not a mapping with text keys. The
values of ``Role`` and ``FinishReason`` are pinned elsewhere and stay as
they are; a call with tools needs no new one.
"""

from __future__ import annotations

import pytest

from ledger_hand.ports import (
    LedgerError,
    LedgerErrorKind,
    ToolCall,
    ToolCallTurn,
    ToolReply,
    ToolResult,
    ToolSpec,
)
from tests.fakes.scripted_model import scripted_record


def test_a_reply_with_no_call_needs_text() -> None:
    with pytest.raises(ValueError):
        ToolReply(text=" ", calls=(), record=scripted_record())

    assert ToolReply(text="", calls=(ToolCall(name="a", arguments={}),), record=scripted_record())


def test_a_tool_call_turn_holds_at_least_one_call() -> None:
    with pytest.raises(ValueError):
        ToolCallTurn(text="", calls=())


@pytest.mark.parametrize("arguments", [["a"], {1: "a"}, "a"])
def test_a_tool_calls_arguments_are_a_mapping_with_text_keys(arguments: object) -> None:
    with pytest.raises(TypeError):
        ToolCall(name="a", arguments=arguments)  # type: ignore[arg-type]


def test_a_tool_needs_a_name_and_a_schema() -> None:
    with pytest.raises(ValueError):
        ToolSpec(name="", description="", parameters={})
    with pytest.raises(TypeError):
        ToolSpec(name="a", description="", parameters="{}")  # type: ignore[arg-type]


def test_a_tool_result_is_a_name_and_text() -> None:
    with pytest.raises(TypeError):
        ToolResult(name="a", content=3)  # type: ignore[arg-type]


def test_a_ledger_error_says_its_kind_code_and_sentence() -> None:
    error = LedgerError(LedgerErrorKind.NOT_FOUND, "trade_not_found", "No such trade.")

    assert str(error) == "not_found (trade_not_found): No such trade."
    assert (error.kind, error.code, error.message) == (
        LedgerErrorKind.NOT_FOUND,
        "trade_not_found",
        "No such trade.",
    )
    assert [kind.value for kind in LedgerErrorKind] == [
        "unreachable",
        "unknown_asset",
        "asset_is_currency",
        "not_found",
        "timed_out",
        "result_unknown",
        "other",
    ]
