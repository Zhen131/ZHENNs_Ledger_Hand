"""The examples the second version of the first prompt adds: shares bought or sold with dollars.

Every passage and every trade here is invented, and the prices are made up.
Between them they show: a share sold in Chinese with the price written as
"美元一股" and no gap before the money; a share bought in English, the time
said as "this morning at" and copied in English; and a coin and a share in
one passage, each with its own money. Every field is copied from its
passage character for character, gaps and all, or left out.

Names defined here: ``SHARE_EXAMPLES`` and ``FIRST_2_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


SHARE_EXAMPLES: tuple[Example, ...] = (
    Example(
        "上周五晚上10点在富途卖了5股NVDA，131.2美元一股，佣金0.99美元",
        (
            _row(
                side="sell",
                coin="NVDA",
                quantity="5股",
                price="131.2美元",
                fee="0.99美元",
                time="上周五晚上10点",
                platform="富途",
            ),
        ),
    ),
    Example(
        "Bought 10 shares of GOOG on Schwab this morning at 10:12, 172.5 USD each, commission 0",
        (
            _row(
                side="buy",
                coin="GOOG",
                quantity="10 shares",
                price="172.5 USD",
                fee="0",
                time="this morning at 10:12",
                platform="Schwab",
            ),
        ),
    ),
    Example(
        (
            "前天上午在OKX买了1.5 ETH，单价2,610 USDT；"
            "晚上8点在富途买了3股NVDA，每股127美元，手续费1美元"
        ),
        (
            _row(
                side="buy",
                coin="ETH",
                quantity="1.5 ETH",
                price="2,610 USDT",
                time="前天上午",
                platform="OKX",
            ),
            _row(
                side="buy",
                coin="NVDA",
                quantity="3股",
                price="127美元",
                fee="1美元",
                time="晚上8点",
                platform="富途",
            ),
        ),
    ),
)

FIRST_2_EXAMPLES: tuple[Example, ...] = (*FIRST_EXAMPLES, *SHARE_EXAMPLES)
