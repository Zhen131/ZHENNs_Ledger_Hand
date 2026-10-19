"""The third prompt version: the first prompt with the two rules of ``second``, and no example more.

It differs from ``first`` in one thing: the two rules of ``second`` come after
the first prompt's instructions, which come before them unchanged: the
owner's words for a buy, and that an amount with U or USDT written right
after it, said neither as the fee nor as the price of one coin, is the total
and never the quantity or the fee. It differs from ``second`` in one thing:
it leaves out the six examples ``second`` adds, so its examples are the
first prompt's ten alone. Set beside ``second``, it shows what the two rules
do without those examples.

The rules are those of ``second``, and the examples and the words for asking
again those of ``first``, taken from them rather than copied; the reply
table is the one every version shares.

Names defined here: ``THIRD_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.second import BUY_WORDS_RULE, U_TOTAL_RULE

THIRD_PROMPT = PromptVersion(
    name="third",
    instructions=FIRST_PROMPT.instructions + BUY_WORDS_RULE + U_TOTAL_RULE,
    examples=FIRST_PROMPT.examples,
    ask_again=FIRST_PROMPT.ask_again,
    reply_table=FIRST_PROMPT.reply_table,
)
