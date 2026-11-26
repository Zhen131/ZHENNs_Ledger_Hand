"""Tests of the fifth version of the assistant's system prompt: the fourth, one rule changed.

The fourth version's rule to list the trades before a change or a
deletion said the opposite of the tools that change and delete, which say
to call them straight away. The fifth keeps every other line of the
fourth as it is, and says what the tools say.
"""

from __future__ import annotations

from ledger_hand.assistant.prompts.assistant_fifth import ASSISTANT_FIFTH
from ledger_hand.assistant.prompts.assistant_fourth import ASSISTANT_FOURTH


def test_the_fifth_version_is_the_fourth_with_one_line_changed() -> None:
    fourth = ASSISTANT_FOURTH.words.splitlines()
    fifth = ASSISTANT_FIFTH.words.splitlines()

    changed = [index for index, line in enumerate(fourth) if fifth[index] != line]
    assert len(fifth) == len(fourth)
    assert [fourth[index] for index in changed] == [
        "- To change or delete a trade, first call list_trades to find it."
    ]


def test_the_changed_line_says_to_call_the_tools_that_change_straight_away() -> None:
    (line,) = [one for one in ASSISTANT_FIFTH.words.splitlines() if one.startswith("- To change")]

    assert "propose_trade_update" in line
    assert "propose_trade_delete" in line
    assert "straight away" in line
    assert "list_trades" not in line
    assert ASSISTANT_FIFTH.name == "assistant-5"
