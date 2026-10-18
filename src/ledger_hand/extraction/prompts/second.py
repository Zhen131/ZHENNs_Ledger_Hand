"""The second prompt version: the first prompt, two more rules and six examples in the owner's way.

It differs from ``first`` in two things at once, so a run of it cannot tell
which of the two made a difference:

- Two rules come after the first prompt's instructions, which come before
  them unchanged: the owner's words for a buy (补, 再补, 补仓, 买到, 买了点),
  and that an amount with U or USDT written right after it, said neither as
  the fee nor as the price of one coin, is the total and never the quantity
  or the fee.
- Six examples come after the first prompt's ten, which come first
  unchanged (``second_examples``). They are written the way the owner
  writes: no space between Chinese and a number, buys only, a long opinion
  before the trade or after it, two trades in one passage.

The words for asking again and the reply table are those of ``first``,
taken from it rather than copied, as are its instructions and examples.

Names defined here: ``SECOND_PROMPT``, ``BUY_WORDS_RULE`` and ``U_TOTAL_RULE``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.second_examples import SECOND_EXAMPLES

# Said after the first prompt's instructions, which come before it unchanged.
BUY_WORDS_RULE = """\
6. These words say a buy as well: 补, 补了, 再补, 补仓, 买到 and 买了点. A trade \
said with one of them has "side" "buy".
"""

# Said after the rule on the words for a buy.
U_TOTAL_RULE = """\
7. A number with U or USDT written right after it, and no 个 and no coin name \
beside it, is the whole amount paid, unless the passage says that this amount \
is the fee (手续费, fee) or the price of one coin (单价, 一个, each, at, @). Copy \
such an amount into total, with its U or USDT, never into quantity or fee, and \
leave quantity "" unless the passage also says how much of the coin.
"""

SECOND_PROMPT = PromptVersion(
    name="second",
    instructions=FIRST_PROMPT.instructions + BUY_WORDS_RULE + U_TOTAL_RULE,
    examples=SECOND_EXAMPLES,
    ask_again=FIRST_PROMPT.ask_again,
    reply_table=FIRST_PROMPT.reply_table,
)
