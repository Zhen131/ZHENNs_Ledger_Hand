"""The examples of the first prompt version: invented passages and the tables they should give.

Every passage and every trade here is invented. None is copied from a real
trade, and the prices are made up for the examples.

Between them they show: Chinese, English and the two mixed; one trade and
several; fields the passage leaves out; passages with no trade at all, with
and without numbers in them; a fee paid in a coin other than USDT; and an
opinion said in the middle of a sentence. In every row, each field is
copied from its passage character for character, or is left out because
the passage does not say it.

Names defined here: ``FIRST_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


FIRST_EXAMPLES: tuple[Example, ...] = (
    Example(
        "昨天晚上 9 点 40 在币安买了 0.02 个比特币，价格 61,250，手续费 1.2 USDT，感觉还会涨",
        (
            _row(
                side="buy",
                coin="比特币",
                quantity="0.02 个比特币",
                price="61,250",
                fee="1.2 USDT",
                time="昨天晚上 9 点 40",
                platform="币安",
                opinion="感觉还会涨",
            ),
        ),
    ),
    Example(
        "Sold 150 SOL at 182.4 on Kraken, taking some profit",
        (
            _row(
                side="sell",
                coin="SOL",
                quantity="150 SOL",
                price="182.4",
                platform="Kraken",
                opinion="taking some profit",
            ),
        ),
    ),
    Example(
        "今天下午 3 点 buy 了 2 ETH @ 3,420 USDT，fee 付的 BNB 0.004",
        (
            _row(
                side="buy",
                coin="ETH",
                quantity="2 ETH",
                price="3,420 USDT",
                fee="0.004",
                fee_currency="BNB",
                time="今天下午 3 点",
            ),
        ),
    ),
    Example(
        "昨天在 OKX 先买了 0.5 ETH，价格 3,380，又买了 200 个 ARB，0.92 一个，两笔手续费都是 0.1U",
        (
            _row(
                side="buy",
                coin="ETH",
                quantity="0.5 ETH",
                price="3,380",
                fee="0.1U",
                time="昨天",
                platform="OKX",
            ),
            _row(
                side="buy",
                coin="ARB",
                quantity="200 个 ARB",
                price="0.92",
                fee="0.1U",
                time="昨天",
                platform="OKX",
            ),
        ),
    ),
    Example(
        "Swapped out of LINK today: sold 40 LINK at 14.6, then bought 0.25 ETH at 2,340",
        (
            _row(
                side="sell",
                coin="LINK",
                quantity="40 LINK",
                price="14.6",
                time="today",
            ),
            _row(
                side="buy",
                coin="ETH",
                quantity="0.25 ETH",
                price="2,340",
                time="today",
            ),
        ),
    ),
    Example("今天行情好无聊，啥也没做，晚上看会儿书", ()),
    Example("BTC touched 70k this morning, crazy. Not touching it.", ()),
    Example("买了点大饼", (_row(side="buy", coin="大饼"),)),
    Example(
        "Bought DOGE for 500 USDT in total on Oct 2, fee was 3 DOGE",
        (
            _row(
                side="buy",
                coin="DOGE",
                total="500 USDT",
                fee="3 DOGE",
                time="Oct 2",
            ),
        ),
    ),
    Example(
        "刚才 sold 0.3 BTC，止盈一部分，at 67.2k",
        (
            _row(
                side="sell",
                coin="BTC",
                quantity="0.3 BTC",
                price="67.2k",
                time="刚才",
                opinion="止盈一部分",
            ),
        ),
    ),
)
