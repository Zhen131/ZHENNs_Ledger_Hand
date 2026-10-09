"""The step-by-step version: the first prompt, asking for a written analysis before the table.

It differs from ``first`` in one thing only: a paragraph after the
instructions asks the model to think step by step first ("chain of
thought"): how many trades the passage reports, and which of quantity,
price of one coin, total or fee each number is. The model writes that
analysis as text in a field of its own, ``steps``, which comes before the
list of rows in its reply table. The reading of a reply leaves ``steps``
aside, as it does every key around the list.

The instructions before the paragraph, the examples and the words for
asking again are those of ``first``, taken from it rather than copied. The
examples' tables have no ``steps``: they show the rows only. It is a
version for experiments; the product records passages with ``first``.

Names defined here: ``STEPWISE_PROMPT``, ``STEPWISE_TABLE``, ``STEPS_KEY``
and ``THINK_FIRST``.
"""

from __future__ import annotations

from collections.abc import Mapping

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.reply_table import REPLY_TABLE, TRADES_KEY

# The key of the written analysis, before the list of rows.
STEPS_KEY = "steps"

# Said after the first prompt's instructions, which come before it unchanged.
THINK_FIRST = """
Before the table, think step by step, and write your thinking as plain text \
in a field "steps" that comes before "trades": first how many trades the \
passage reports, then, for every number in the passage, whether it is a \
quantity, the price of one coin, the total, the fee, or none of these. Then \
fill "trades" by the rules above. So the reply is one JSON object: \
{"steps": "...", "trades": [...]}.
"""

_ROWS = REPLY_TABLE["properties"]
assert isinstance(_ROWS, Mapping)

STEPWISE_TABLE: Mapping[str, object] = {
    "type": "object",
    "properties": {STEPS_KEY: {"type": "string"}, TRADES_KEY: _ROWS[TRADES_KEY]},
    "required": [STEPS_KEY, TRADES_KEY],
    "additionalProperties": False,
}

STEPWISE_PROMPT = PromptVersion(
    name="stepwise",
    instructions=FIRST_PROMPT.instructions + THINK_FIRST,
    examples=FIRST_PROMPT.examples,
    ask_again=FIRST_PROMPT.ask_again,
    reply_table=STEPWISE_TABLE,
)
