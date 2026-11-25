"""The third version of the first prompt: the second one's words, the quantity copied whole.

Measured on the share set, the second version (``first2``) fixed the gaps
it was written for, but the model then copied "2 shares" out of "2 MSFT
shares", which is not a piece of the passage, and left the coin empty when
USDT itself was bought. This version keeps the second one's words and
changes two places: the quantity is copied with every word written right
after the number ("2 ETH", "3股", "10 GOOG shares"), and the coin may itself
be a money such as USDT. Its English share example says the quantity that
way (``first3_examples``).

Only the assistant extracts with this version; the record page keeps the
first one.

A version is never changed once it has been measured; a change of wording is
a new version in a new file.

This version is named ``first-3``.

Names defined here: ``FIRST_PROMPT_3``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PROBLEM_MARK, PromptVersion
from ledger_hand.extraction.prompts.first3_examples import FIRST_3_EXAMPLES

_INSTRUCTIONS = """\
You copy the details of spot trades (coins, shares or other assets) out of a \
short passage that one person wrote about their own trades. You never calculate, \
convert, translate, correct or guess anything.

Reply with one JSON object: {"trades": [...]}, with one row for each trade \
the passage mentions. If it mentions no trade, reply {"trades": []}.

Every row has the same eleven fields. "side" is "buy" when the coin or share was bought \
(bought, buy, 买, 买入, 加仓), "sell" when it was sold (sold, sell, 卖, 卖出, \
止盈, 清仓), and "" when the passage does not say. Every other field holds a \
piece of the passage copied character for character, or "" when the passage \
does not say it:

- coin: the coin, share or other asset bought or sold, as the passage calls it; \
it may itself be a money, such as USDT.
- quantity: how much of it: the number, with every word written right after it \
that says what it counts ("2 ETH", "3股", "10 GOOG shares").
- price: the price of one coin or one share: the number, with the currency \
sign or word written right next to it if there is one.
- total: the whole amount paid or received, without the fee: the number, with \
the currency sign or word written right next to it if there is one.
- price_currency: the currency of the price or total, only when the passage \
names it apart from those numbers.
- fee: the fee: the number, with the currency word written right after it if \
there is one.
- fee_currency: the currency the fee was paid in, only when the passage names \
it apart from the fee's number.
- time: when the trade happened: only the words that say the day and the time, \
in the passage's own words ("last night", "昨天晚上 9 点 40", "Oct 2 at 14:05").
- platform: the exchange or app the trade was made on.
- opinion: the person's own view, reason or feeling about the trade.

Rules:
1. Copy, never rewrite. Keep every digit, comma, point, letter, unit and word \
exactly as the passage writes it. Never translate: what you copy from English \
words stays English, and what you copy from Chinese words stays Chinese. Do not \
turn Chinese numbers into digits or digits into words, and never drop a "k", a \
"w" or a "万" from a number.
2. Leave a field "" when the passage does not say it. Never fill in a market \
price, a date, a fee or a currency the passage does not write.
3. Each field is one unbroken piece of the passage.
4. A detail said once for several trades, such as the day, the exchange or a \
shared fee, is copied into each of those rows.
5. Each row holds only what belongs to its own trade. Two coins or shares, or \
two separate buys or sells, are two rows.
6. Copy the gaps as they are: where the passage writes "88美元" with no gap, \
copy "88美元", never "88 美元".
"""

_ASK_AGAIN = (
    f"Your last answer could not be used: {PROBLEM_MARK}. Answer again with only "
    'the JSON object {"trades": [...]}, following the rules above.'
)

FIRST_PROMPT_3 = PromptVersion(
    name="first-3",
    instructions=_INSTRUCTIONS,
    examples=FIRST_3_EXAMPLES,
    ask_again=_ASK_AGAIN,
)
