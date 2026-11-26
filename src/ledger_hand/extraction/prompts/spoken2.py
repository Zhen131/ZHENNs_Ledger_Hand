"""The second version for Chinese: ``first-3``'s words, rules for the owner's way, more examples.

Measured on the practice half of the exam said the owner's way, ``spoken-1``
fixed what it was written for, but copied a time zone said at the end of
a passage ("布达佩斯时间") as the platform, and once put a total said as
"一共花了" into the price. On the final set it wrote a remark about the
market as the trade's opinion, which counts as a value made up: its rule
to copy every amount the passage says did not say "of the trade". This
version keeps every word of ``first-3``; its rules are those of
``spoken-1`` with that one narrowed to the trade's own amounts, and the
words for a price and a total listed more fully, a rule that a time zone
is never the platform, and one that a remark about the market is not the
trade's opinion. It keeps ``spoken-1``'s three examples and adds
three (``spoken2_examples``).

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``spoken-2``.

Names defined here: ``SPOKEN_PROMPT_2``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.spoken2_examples import SPOKEN_2_EXAMPLES

_SPOKEN_RULES = """\
7. Money spent on a coin or share is a buy, even with no word for buying \
("…个ETH，花了…U" is "buy"); money got for it is a sell.
8. The money spent or got for the whole trade is the total, never the price, \
wherever it stands: "花了612.4U" after the quantity, "一共花了…", "总额…", \
"成交额…" and "委托的价值…" are the total. The price is the money for one coin \
or one share: "均价…", "成交价…", "单价…", "一股…", "每个…", "…一个", "…一股".
9. Money said before "的" and the coin ("300美金的DOT") is the total.
10. Copy each amount of the trade itself (quantity, price, total, fee) that \
the passage says, the total too, even when the quantity and the price are \
said as well. A number about anything else is not copied.
11. A number in number words followed by the coin ("零点二五一个ETH") is the \
quantity: copy it whole, words and all.
12. A time zone said by name ("布达佩斯时间", "匈牙利时间") is never the \
platform. The platform is an exchange or app, such as 币安, OKX or IBKR.
13. The opinion is only the person's own view of this trade. A remark about \
the market or another coin at the time ("那天比特币刚过10万") is not an \
opinion: leave it out.
"""

SPOKEN_PROMPT_2 = PromptVersion(
    name="spoken-2",
    instructions=FIRST_PROMPT_3.instructions + _SPOKEN_RULES,
    examples=SPOKEN_2_EXAMPLES,
    ask_again=FIRST_PROMPT_3.ask_again,
)
