"""The third version for Chinese: the second one, with the opinion copied only when said so.

Measured, ``spoken-2`` sent no wrong figure without a mark on the practice
half of the exam said the owner's way, and did not pass the final set for
one reason only: it still wrote a remark about the market as the trade's
opinion, a value made up, although its last rule said not to. This
version keeps every word of ``first-3`` and every example of ``spoken-2``;
its rules are those of ``spoken-2`` with the last one made firmer: the
opinion is left out unless the person says why they made the trade or how
they feel about it, in words such as 感觉, 觉得 or 因为. One example is
added that holds both such a view and a remark about another coin
(``spoken3_examples``).

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``spoken-3``.

Names defined here: ``SPOKEN_PROMPT_3``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.spoken3_examples import SPOKEN_3_EXAMPLES

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
13. Leave the opinion "" unless the person says why they made this trade or \
how they feel about it, in words such as 感觉, 觉得, 因为, 看好, 止盈 or 补仓 \
("感觉还能涨"). What a coin or the market was doing at the time ("那天以太跌了\
不少") is not an opinion: never copy it.
"""

SPOKEN_PROMPT_3 = PromptVersion(
    name="spoken-3",
    instructions=FIRST_PROMPT_3.instructions + _SPOKEN_RULES,
    examples=SPOKEN_3_EXAMPLES,
    ask_again=FIRST_PROMPT_3.ask_again,
)
