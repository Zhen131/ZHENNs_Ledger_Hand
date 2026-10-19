"""The fourth prompt version: the first prompt, the two rules of ``second`` and seven new examples.

It differs from ``first`` in two things at once, so a run of it cannot tell
which of the two made a difference:

- The two rules of ``second`` come after the first prompt's instructions,
  which come before them unchanged: the owner's words for a buy, and that an
  amount with U or USDT written right after it, said neither as the fee nor
  as the price of one coin, is the total and never the quantity or the fee.
- Seven examples come after the first prompt's ten, which come first
  unchanged (``fourth_examples``): five written the way the owner writes,
  one of them with a price in Chinese numbers, and two in English only, with
  an English time and a quantity written as a bare number or with an English
  coin name.

It differs from ``third`` only in the seven examples, which ``third`` does
not have, and from ``second`` only in its examples: the seven take the place
of the six that ``second`` adds, none of which is used here.

The rules are those of ``second``, and the words for asking again those of
``first``, taken from them rather than copied; the reply table is the one
every version shares.

Names defined here: ``FOURTH_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.fourth_examples import FOURTH_EXAMPLES
from ledger_hand.extraction.prompts.second import BUY_WORDS_RULE, U_TOTAL_RULE

FOURTH_PROMPT = PromptVersion(
    name="fourth",
    instructions=FIRST_PROMPT.instructions + BUY_WORDS_RULE + U_TOTAL_RULE,
    examples=FOURTH_EXAMPLES,
    ask_again=FIRST_PROMPT.ask_again,
    reply_table=FIRST_PROMPT.reply_table,
)
