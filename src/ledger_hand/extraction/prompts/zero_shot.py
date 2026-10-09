"""The zero-shot version: the first prompt's instructions with no example at all.

It differs from ``first`` in one thing only: it shows the model no example.
The instructions and the words for asking again are those of ``first``,
taken from it rather than copied, so the two cannot drift apart. It is a
version for experiments; the product records passages with ``first``.

Names defined here: ``ZERO_SHOT_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT

ZERO_SHOT_PROMPT = PromptVersion(
    name="zero_shot",
    instructions=FIRST_PROMPT.instructions,
    examples=(),
    ask_again=FIRST_PROMPT.ask_again,
)
