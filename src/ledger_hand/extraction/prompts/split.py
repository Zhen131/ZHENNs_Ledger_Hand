"""The prompt that splits a passage: for each trade, the pieces of the passage it needs. Few-shot.

Used only when a passage is split before extraction (``splitting``), which
the experiments compare with the one call the product makes. The model gets
instructions and five invented examples, shown as earlier turns of the
conversation (a few examples, "few-shot"), and answers with one item per
trade, each a list of pieces copied out of the passage, which the model
server holds to the schema in ``split_table``.

The points of this version:

- The model only copies: each piece is one unbroken run of the passage,
  never rewritten or translated. The program checks that every piece really
  is a piece of the passage, and builds each trade's segment from the
  passage's own text.
- A detail said once for several trades (the day, the exchange, a shared
  fee) is copied into the pieces of each of them, so that every segment
  still says it.
- A passage that reports one trade is one item with no piece, since there
  is nothing to cut; a passage with no trade is an empty list.

A version is never changed once it has been measured; a change of wording is
a new version in a new file. Every example is invented: none is copied from
a real trade, nor from a test sentence.

This version is named ``split-1``.

Names defined here: ``SPLIT_PROMPT``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import PROBLEM_MARK
from ledger_hand.extraction.split_table import SplitExample, SplitPromptVersion

_INSTRUCTIONS = """\
You read a short passage that one person wrote about their own crypto spot \
trades, and you cut it into one part for each trade it reports. You never \
rewrite, translate, correct, calculate or explain anything.

Reply with one JSON object: {"trades": [{"pieces": [...]}, ...]}, with one item \
for each trade the passage reports, in the order the passage reports them. If \
it reports no trade, reply {"trades": []}.

The "pieces" of a trade are the pieces of the passage that this trade needs:
- the words that say whether it was bought or sold, which coin, how much, and \
its price or total;
- every detail said once for several trades, such as the day and the time, the \
exchange, a shared fee, or a feeling about all of them: copy it into the pieces \
of each of those trades.
Leave out what belongs only to another trade, and words that only count the \
trades.

Rules:
1. Copy, never rewrite. Each piece is one unbroken run of the passage, copied \
character for character: keep every digit, comma, point, space, letter and word \
exactly as written, and leave no word out of the middle of a piece. Never \
translate.
2. Never join words that stand apart in the passage into one piece. A word said \
once for several trades is a piece of its own in each of them: in "sold 1 X and \
2 Y", the pieces of the second trade are "sold" and "2 Y", never "sold 2 Y".
3. Give the pieces of a trade in the order they stand in the passage.
4. Two coins, or two separate buys or sells, are two trades. A feeling, a reason \
or a plan is never a trade of its own: it goes into the pieces of the trades it \
is about.
5. When the passage reports one trade only, there is nothing to cut: reply \
{"trades": [{"pieces": []}]}.
"""

_ASK_AGAIN = (
    f"Your last answer could not be used: {PROBLEM_MARK}. Answer again with only "
    'the JSON object {"trades": [{"pieces": [...]}, ...]}, following the rules above.'
)

_EXAMPLES = (
    SplitExample(
        "昨天晚上在 Gate 操作了两次：先卖了 3 个 AVAX，价格 27.5，后来又买了 60 个 ATOM "
        "单价 6.9，手续费各 0.2U，都是短线",
        (
            ("昨天晚上在 Gate", "卖了 3 个 AVAX，价格 27.5", "手续费各 0.2U，都是短线"),
            ("昨天晚上在 Gate", "买了 60 个 ATOM 单价 6.9", "手续费各 0.2U，都是短线"),
        ),
    ),
    SplitExample(
        "This afternoon on Bitstamp I sold 2 LTC at 72.4, then bought 1.5 BNB at 591 and "
        "40 DOT at 4.35, fee 0.2 USDT on every trade",
        (
            ("This afternoon on Bitstamp", "sold 2 LTC at 72.4", "fee 0.2 USDT on every trade"),
            (
                "This afternoon on Bitstamp",
                "bought 1.5 BNB at 591",
                "fee 0.2 USDT on every trade",
            ),
            (
                "This afternoon on Bitstamp",
                "bought",
                "40 DOT at 4.35",
                "fee 0.2 USDT on every trade",
            ),
        ),
    ),
    SplitExample(
        "上午买了 0.1 个 ETH，价格 3,050，又花了 200U 买了 SUI，都在币安",
        (
            ("上午买了 0.1 个 ETH，价格 3,050", "都在币安"),
            ("上午", "又花了 200U 买了 SUI", "都在币安"),
        ),
    ),
    SplitExample("前天 sold 0.4 个 BNB at 593 on OKX，fee 0.05 USDT", ((),)),
    SplitExample("今天一直在看盘，一单都没下", ()),
)

SPLIT_PROMPT = SplitPromptVersion(
    name="split-1",
    instructions=_INSTRUCTIONS,
    examples=_EXAMPLES,
    ask_again=_ASK_AGAIN,
)
