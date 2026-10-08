"""The prompt that judges a passage: which kinds of thing it reports. Zero-shot.

The technique is zero-shot: the model gets instructions only, and not one
example. It is told one fixed list of kinds (a filled spot trade; futures or
leverage; one coin swapped for another; an order not filled yet; a plan) and
what each means, and it answers with a flat list of reports, one kind and a
piece of the passage as evidence each, which the model server holds to the
schema in ``screen_table``. It never rewrites or translates the passage: the
evidence is copied, and the program checks that it really is a piece of the
passage before quoting it.

What the program does with the answer (stop the passage, say there is no
trade, or go on to extraction) is decided in ``screening``, not by the model.

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``screen-1``; the state of a recorded passage names it
for the step it was used in.

Names defined here: ``SCREEN_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PROBLEM_MARK, PromptVersion

_INSTRUCTIONS = """\
You read a short passage that one person wrote about their own crypto \
trading, and you say what kinds of thing it reports. You never rewrite, \
translate or explain the passage.

The kinds:
- "spot_trade": a spot buy or sell of a coin that has already happened: the \
coin was bought or sold, and the order is filled.
- "futures_or_leverage": trading futures, perpetual contracts or on margin: \
leverage such as 5x, opening or closing a long or short position, a \
liquidation.
- "coin_for_coin": one coin swapped or exchanged directly for another coin, \
instead of being bought or sold for USDT or dollars.
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

SCREEN_PROMPT = PromptVersion(
    name="screen-1",
    instructions=_INSTRUCTIONS,
    examples=(),
    ask_again=_ASK_AGAIN,
)
