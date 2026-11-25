"""The second prompt that judges a passage: the first one's words, not limited to crypto.

The first version (``screen``) tells the model the passage is about crypto
trading and that a spot trade is a coin bought or sold. Measured on
sentences about a share bought with US dollars, it judged some of them to
report no trade at all. This version keeps every word of the first one but
those: the passage is about the person's own trading, and a spot trade is a
coin, a share or another asset bought or sold. The technique is the same:
zero-shot, one fixed list of kinds, evidence copied, never rewritten.

Only the assistant judges with this version; the record page keeps the
first one.

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``screen-2``; the state of a recorded passage names it
for the step it was used in.

Names defined here: ``SCREEN_PROMPT_2``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PROBLEM_MARK, PromptVersion

_INSTRUCTIONS = """\
You read a short passage that one person wrote about their own trading (coins, \
shares or other assets), and you say what kinds of thing it reports. You never \
rewrite, translate or explain the passage.

The kinds:
- "spot_trade": a spot buy or sell of a coin, a share or another asset that \
has already happened: it was bought or sold, and the order is filled.
- "futures_or_leverage": trading futures, perpetual contracts or on margin: \
leverage such as 5x, opening or closing a long or short position, a \
liquidation.
- "coin_for_coin": one coin swapped or exchanged directly for another coin, \
instead of being bought or sold for money such as USDT or dollars.
- "open_order": an order that has been placed but is not filled yet, such as \
a limit order that is still waiting.
- "plan": something the person intends, plans or hopes to do later, not \
something that has happened.

Reply with one JSON object: {"reports": [...]}. Add one report for each thing \
in the passage that is one of these kinds: {"kind": "<one of the kinds \
above>", "evidence": "<the words of the passage that show it>"}. The evidence \
is one unbroken piece of the passage, copied character for character, never \
rewritten or translated. A passage may report several kinds at once. If it \
reports none of them (small talk, a question, a price with no trade of the \
person's own), reply {"reports": []}.
"""

_ASK_AGAIN = (
    f"Your last answer could not be used: {PROBLEM_MARK}. Answer again with only "
    'the JSON object {"reports": [...]}, following the rules above.'
)

SCREEN_PROMPT_2 = PromptVersion(
    name="screen-2",
    instructions=_INSTRUCTIONS,
    examples=(),
    ask_again=_ASK_AGAIN,
)
