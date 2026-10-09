"""The price-and-total version: the first prompt with one more rule, on price and total.

It differs from ``first`` in one thing only: a sixth rule after the
instructions says how the price of one coin and the total of a trade are
told apart, and that an amount said as a total is never copied into the
price. The instructions before it, the examples and the words for asking
again are those of ``first``, taken from it rather than copied. It is a
version for experiments; the product records passages with ``first``.

Names defined here: ``PRICE_TOTAL_PROMPT`` and ``PRICE_TOTAL_RULE``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT

# Said after the first prompt's instructions, which come before it unchanged.
PRICE_TOTAL_RULE = """\
6. Price and total are two different fields. The price is what one coin \
cost; the total is what the whole trade came to. An amount said as a total \
("一共", "总共", "花了", "total", "in total", or "for" an amount of money \
rather than "at" a price) goes into total, never into price. Leave price "" \
unless the passage also says what one coin cost.
"""

PRICE_TOTAL_PROMPT = PromptVersion(
    name="price_total",
    instructions=FIRST_PROMPT.instructions + PRICE_TOTAL_RULE,
    examples=FIRST_PROMPT.examples,
    ask_again=FIRST_PROMPT.ask_again,
)
