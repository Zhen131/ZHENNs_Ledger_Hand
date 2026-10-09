"""Tests of a prompt version's own reply table: extraction hands the model the version's table.

A version that names no table keeps ``REPLY_TABLE``, the very same object,
so the first prompt sends what it always sent (the sample of its calls
checks that byte for byte). A version may bring a table with a key around
the list of rows; the reply is read as before, the extra key left aside.
Every passage and reply here is invented.
"""

from __future__ import annotations

import json

from ledger_hand.extraction.extractor import Extracted
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.reply_table import REPLY_TABLE
from tests.extraction.scripted_runs import row, run

OWN_TABLE = {
    "type": "object",
    "properties": {
        "notes": {"type": "string"},
        "trades": REPLY_TABLE["properties"]["trades"],  # type: ignore[index]
    },
    "required": ["notes", "trades"],
    "additionalProperties": False,
}
WITH_OWN_TABLE = PromptVersion(
    name="own-table",
    instructions=FIRST_PROMPT.instructions,
    examples=(),
    ask_again=FIRST_PROMPT.ask_again,
    reply_table=OWN_TABLE,
)
PASSAGE = "昨天买了 0.2 ETH，价格 3,200"
ROW = row(side="buy", coin="ETH", quantity="0.2 ETH", price="3,200", time="昨天")


def test_a_version_that_names_no_table_keeps_the_reply_table_itself() -> None:
    plain = PromptVersion("plain", "x", (), FIRST_PROMPT.ask_again)

    assert plain.reply_table is REPLY_TABLE
    assert FIRST_PROMPT.reply_table is REPLY_TABLE


def test_the_first_prompt_sends_the_reply_table() -> None:
    _, model = run(PASSAGE, json.dumps({"trades": [ROW]}))

    (call,) = model.calls
    assert call.reply_schema is REPLY_TABLE


def test_a_version_with_its_own_table_sends_that_table_every_time() -> None:
    _, model = run(
        PASSAGE,
        "not JSON",
        json.dumps({"notes": "one trade", "trades": [ROW]}),
        prompt=WITH_OWN_TABLE,
    )

    assert [call.reply_schema for call in model.calls] == [OWN_TABLE, OWN_TABLE]
    assert all(call.reply_schema is OWN_TABLE for call in model.calls)


def test_a_key_around_the_rows_is_left_aside_and_the_rows_are_read() -> None:
    with_notes, _ = run(
        PASSAGE, json.dumps({"notes": "one trade", "trades": [ROW]}), prompt=WITH_OWN_TABLE
    )
    without, _ = run(PASSAGE, json.dumps({"trades": [ROW]}), prompt=WITH_OWN_TABLE)

    assert isinstance(with_notes, Extracted) and isinstance(without, Extracted)
    assert with_notes.drafts == without.drafts
    assert with_notes.issues == without.issues
