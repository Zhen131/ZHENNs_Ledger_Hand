"""The first version for Chinese: the third version's words, and the owner's way of speaking.

The assistant reads words with a Chinese character in them with a version
of its own (``extraction.prompt_language``); English keeps ``first-3``.
Measured on the practice half of the exam said the owner's way, ``first-3``
asked whether a trade was a buy when the words spent money on a coin with
no word for buying, put money spent after the quantity ("…个ETH 花了…U")
into the price, and left out a total said as "…美金的ADA", so the program
worked one out that was a little off. This version keeps every word of
``first-3`` and adds a few rules for those, and three examples written the
way the owner speaks, already tidied (``spoken1_examples``). The rules
added also say that a quantity in number words, which tidying leaves as it
is when it ends in "一个", is copied whole: ``first-3`` put one into the
price.

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``spoken-1``.

Names defined here: ``SPOKEN_PROMPT_1``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.spoken1_examples import SPOKEN_1_EXAMPLES

_SPOKEN_RULES = """\
7. Money spent on a coin or share is a buy, even with no word for buying \
("…个ETH，花了…U" is "buy"); money got for it is a sell.
8. The money spent or got for the whole trade is the total, never the price, \
wherever it stands: "花了612.4U" after the quantity is the total. The price is \
the money for one coin or one share, said with words such as 均价, 成交价, 单价, \
一股 or 每个.
9. Money said before "的" and the coin ("300美金的DOT") is the total.
10. Copy every amount the passage says, the total too, even when the quantity \
and the price are said as well.
11. A number in number words followed by the coin ("零点二五一个ETH") is the \
quantity: copy it whole, words and all.
"""

SPOKEN_PROMPT_1 = PromptVersion(
    name="spoken-1",
    instructions=FIRST_PROMPT_3.instructions + _SPOKEN_RULES,
    examples=SPOKEN_1_EXAMPLES,
    ask_again=FIRST_PROMPT_3.ask_again,
)
