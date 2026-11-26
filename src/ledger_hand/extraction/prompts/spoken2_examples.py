"""The examples the second version for Chinese adds: the first one's, and three more.

Every passage and every trade here is invented, and the prices are made up.
Each passage is written as the program hands it to the model, already
tidied. The three added show: a time zone said at the end of the passage
("匈牙利时间"), which is part of the time and never the platform; a total
said as "一共花了"; and a price said as so much "一个", with the fee in U and
a remark about the market at the time, which is not the trade's opinion.
Every field is copied from its passage character for character, gaps and
all, or left out.

Names defined here: ``SPOKEN_EXAMPLES_2`` and ``SPOKEN_2_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.prompts.first3_examples import FIRST_3_EXAMPLES
from ledger_hand.extraction.prompts.spoken1_examples import SPOKEN_EXAMPLES_1
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


SPOKEN_EXAMPLES_2: tuple[Example, ...] = (
    Example(
        "2026年8月14号晚上19点26分，我把41.2个DOT卖了，均价6.824U，收了我0.03U手续费，匈牙利时间。",
        (
            _row(
                side="sell",
                coin="DOT",
                quantity="41.2个DOT",
                price="6.824U",
                fee="0.03U",
                time="2026年8月14号晚上19点26分",
            ),
        ),
    ),
    Example(
        "2026年8月12日16:05，币安，买入0.0861 ETH，扣了0.21 USDT手续费，一共花了210.5 USDT。",
        (
            _row(
                side="buy",
                coin="ETH",
                quantity="0.0861 ETH",
                total="210.5 USDT",
                fee="0.21 USDT",
                time="2026年8月12日16:05",
                platform="币安",
            ),
        ),
    ),
    Example(
        "我在2026年8月9号下午15点12分把12个LINK卖了，14.35一个，手续费0.2U，那天比特币刚过10万。",
        (
            _row(
                side="sell",
                coin="LINK",
                quantity="12个LINK",
                price="14.35",
                fee="0.2U",
                time="2026年8月9号下午15点12分",
            ),
        ),
    ),
)

SPOKEN_2_EXAMPLES: tuple[Example, ...] = (
    *FIRST_3_EXAMPLES,
    *SPOKEN_EXAMPLES_1,
    *SPOKEN_EXAMPLES_2,
)
