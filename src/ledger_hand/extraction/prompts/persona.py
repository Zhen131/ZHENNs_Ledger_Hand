"""The persona version: the first prompt with a role said before its instructions.

It differs from ``first`` in one thing only: a short paragraph at the very
start gives the model a role, a meticulous bookkeeper. The instructions
after it, the examples and the words for asking again are those of
``first``, taken from it rather than copied. It is a version for
experiments; the product records passages with ``first``.

Names defined here: ``PERSONA_PROMPT`` and ``ROLE``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT

# Said before the first prompt's instructions, which follow it unchanged.
ROLE = """\
You are a meticulous bookkeeper who keeps the trading journal of one person. \
You take great care that every entry holds exactly what that person wrote, \
nothing more and nothing less, and you would rather leave a field empty than \
put a doubtful word in it.

"""

PERSONA_PROMPT = PromptVersion(
    name="persona",
    instructions=ROLE + FIRST_PROMPT.instructions,
    examples=FIRST_PROMPT.examples,
    ask_again=FIRST_PROMPT.ask_again,
)
