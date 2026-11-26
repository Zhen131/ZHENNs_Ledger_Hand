"""The examples the first version for Chinese adds: trades said the way the owner speaks.

Every passage and every trade here is invented, and the prices are made up.
Each passage is written as the program hands it to the model, already
tidied: number words as digits, a time said in Chinese written in digits.
Between them they show: a coin with money spent on it and no word for
buying, the money spent after the quantity copied as the total, and a
quantity in number words, which tidying leaves as it is, copied whole;
money said before "的" and the coin ("300美金的DOT") copied as the total,
with the price and the quantity also said; and the fee's coin said apart
from its number. Every field is copied from its passage character for character,
gaps and all, or left out.

Names defined here: ``SPOKEN_EXAMPLES_1`` and ``SPOKEN_1_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.prompts.first3_examples import FIRST_3_EXAMPLES
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


SPOKEN_EXAMPLES_1: tuple[Example, ...] = (
    Example(
        "那天2026年8月3号晚上21点16分在币安上，零点二五一个ETH，花了612.4U，手续费是零。",
        (
            _row(
                side="buy",
                coin="ETH",
                quantity="零点二五一个ETH",
                total="612.4U",
                fee="零",
                time="2026年8月3号晚上21点16分",
                platform="币安",
            ),
        ),
    ),
    Example(
        (
            "2026年8月19号下午16点40分我又买入了300美金的DOT，均价是4.125 USDT，"
            "成交量72.72个DOT，手续费呢是0.07，手续费的DOT。"
        ),
        (
            _row(
                side="buy",
                coin="DOT",
                quantity="72.72个DOT",
                price="4.125 USDT",
                total="300美金",
                fee="0.07",
                fee_currency="DOT",
                time="2026年8月19号下午16点40分",
            ),
        ),
    ),
    Example(
        "2026年8月21日09:12买入80美金的XRP，成交价0.5312 USDT，数量150.6 XRP，手续费0.15 XRP。",
        (
            _row(
                side="buy",
                coin="XRP",
                quantity="150.6 XRP",
                price="0.5312 USDT",
                total="80美金",
                fee="0.15 XRP",
                time="2026年8月21日09:12",
            ),
        ),
    ),
)

SPOKEN_1_EXAMPLES: tuple[Example, ...] = (*FIRST_3_EXAMPLES, *SPOKEN_EXAMPLES_1)
