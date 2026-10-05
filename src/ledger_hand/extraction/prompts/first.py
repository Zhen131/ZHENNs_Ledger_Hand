"""The first prompt version: copy, never compute; one row per trade; empty when not said.

The points of this version:

- The model copies phrases; it never calculates, converts, translates,
  corrects or guesses. The program does all of that afterwards, and checks
  that every phrase really is a piece of the passage.
- A field the passage does not state stays empty. No market price, no date,
  no fee and no currency is filled in.
- A number is copied together with the unit or currency word written right
  next to it, so that "6万刀" or "2 USDT" keeps its unit; a currency named
  elsewhere goes in its own field.
- One call gives the whole list: one row per trade, and an empty list when
  the passage reports none. A detail said once for several trades is copied
  into each of them.
- The instructions are in English; the examples are in Chinese, in English
  and in the two mixed. The examples are shown as earlier turns of the
  conversation (a few examples, "few-shot").
- Plans, open orders and futures are not singled out: this version does not
  ask the model to leave them out, which is decided later.

Names defined here: ``FIRST_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PROBLEM_MARK, PromptVersion
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES

_INSTRUCTIONS = """\
You copy the details of crypto spot trades out of a short passage that one \
person wrote about their own trades. You never calculate, convert, translate, \
correct or guess anything.

Reply with one JSON object: {"trades": [...]}, with one row for each trade \
the passage mentions. If it mentions no trade, reply {"trades": []}.

Every row has the same eleven fields. "side" is "buy" when the coin was bought \
(bought, buy, 买, 买入, 加仓), "sell" when it was sold (sold, sell, 卖, 卖出, \
止盈, 清仓), and "" when the passage does not say. Every other field holds a \
piece of the passage copied character for character, or "" when the passage \
does not say it:

- coin: the coin bought or sold, as the passage calls it.
- quantity: how much of the coin: the number, with the unit written right \
after it if there is one.
- price: the price of one coin: the number, with the currency sign or word \
written right next to it if there is one.
- total: the whole amount paid or received, without the fee: the number, with \
the currency sign or word written right next to it if there is one.
- price_currency: the currency of the price or total, only when the passage \
names it apart from those numbers.
- fee: the fee: the number, with the currency word written right after it if \
there is one.
- fee_currency: the currency the fee was paid in, only when the passage names \
it apart from the fee's number.
- time: when the trade happened: only the words that say the day and the time.
- platform: the exchange or app the trade was made on.
- opinion: the person's own view, reason or feeling about the trade.

Rules:
1. Copy, never rewrite. Keep every digit, comma, point, letter, unit and word \
exactly as the passage writes it. Do not turn Chinese numbers into digits or \
digits into words, and never drop a "k", a "w" or a "万" from a number.
2. Leave a field "" when the passage does not say it. Never fill in a market \
price, a date, a fee or a currency the passage does not write.
3. Each field is one unbroken piece of the passage.
4. A detail said once for several trades, such as the day, the exchange or a \
shared fee, is copied into each of those rows.
5. Each row holds only what belongs to its own trade. Two coins, or two \
separate buys or sells, are two rows.
"""

_ASK_AGAIN = (
    f"Your last answer could not be used: {PROBLEM_MARK}. Answer again with only "
    'the JSON object {"trades": [...]}, following the rules above.'
)

FIRST_PROMPT = PromptVersion(
    name="first",
    instructions=_INSTRUCTIONS,
    examples=FIRST_EXAMPLES,
    ask_again=_ASK_AGAIN,
)
