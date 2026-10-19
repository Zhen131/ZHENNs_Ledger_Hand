"""The examples of the fourth prompt version: the first prompt's ten, then seven written anew.

``FOURTH_EXAMPLES`` is the first prompt's examples, the very same objects in
the same order, followed by ``ADDED_EXAMPLES``. Every passage and every
trade of these seven is invented, and so is every opinion in them; none is
copied from a real trade, from a test sentence or from another version's
examples. Every one is a buy on OKX with the fee paid in the coin bought.
The five with Chinese in them are written the way the owner writes: no
space between Chinese and a number. Two are in English only, written with
their spaces.

Between them they show:

- an amount with U right after it that is the total, with no quantity said
  ("补了60U", "45U买了点LINK", "再补30U");
- a long opinion of several clauses, with a percentage in it that is not
  the trade's price, said before the trade or after it, copied whole but
  without the mark that sets it apart from the trade;
- a quantity, a price and a fee written right against the Chinese
  ("成交1.42个", "15.3一个", "手续费0.00142AVAX");
- 买到, 买了点, 补仓 and a limit order that was filled, each a buy;
- two trades in one passage that share the time and the exchange, each with
  an opinion of its own in its own part of the passage;
- a price written in Chinese numbers ("五万九千八"), copied as written, never
  turned into digits;
- English passages with an English time ("this morning", "yesterday"),
  copied in English, never put into Chinese; and a quantity written as a
  bare number ("20") or with an English coin name ("3.2 ATOM"), copied as
  written, with no 个 and no Chinese added.

In every row, each field is copied from its passage character for
character, or is left out because the passage does not say it; a currency
written next to a number is not copied again into a field of its own.

Names defined here: ``FOURTH_EXAMPLES`` and ``ADDED_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


ADDED_EXAMPLES: tuple[Example, ...] = (
    Example(
        "这个月工资到账了，照老规矩拿出10%换成币。周日晚上10点在OKX补了60U的SOL，138.4一个，"
        "手续费0.00043SOL",
        (
            _row(
                side="buy",
                coin="SOL",
                price="138.4",
                total="60U",
                fee="0.00043SOL",
                time="周日晚上10点",
                platform="OKX",
                opinion="这个月工资到账了，照老规矩拿出10%换成币",
            ),
        ),
    ),
    Example(
        "昨晚21:15在OKX用45U买了点LINK，15.3一个，手续费0.0029LINK。"
        "它上个月涨了20%又全跌回去，想先拿一点慢慢加",
        (
            _row(
                side="buy",
                coin="LINK",
                price="15.3",
                total="45U",
                fee="0.0029LINK",
                time="昨晚21:15",
                platform="OKX",
                opinion="它上个月涨了20%又全跌回去，想先拿一点慢慢加",
            ),
        ),
    ),
    Example(
        "上周给AVAX挂了个限价单，打算拿去参加链上活动。"
        "前天下午2点OKX提示触发后成交1.42个，均价28.15，共40USDT，手续费0.00142AVAX",
        (
            _row(
                side="buy",
                coin="AVAX",
                quantity="1.42个",
                price="28.15",
                total="40USDT",
                fee="0.00142AVAX",
                time="前天下午2点",
                platform="OKX",
                opinion="上周给AVAX挂了个限价单，打算拿去参加链上活动",
            ),
        ),
    ),
    Example(
        "周五晚上9点在OKX分了两笔：ETH这周回调得有点多，补仓30USDT买到0.0127个，均价2,362，"
        "手续费0.0000127ETH；DOGE纯属手痒，20USDT买了92个，0.2174一个，手续费0.092DOGE",
        (
            _row(
                side="buy",
                coin="ETH",
                quantity="0.0127个",
                price="2,362",
                total="30USDT",
                fee="0.0000127ETH",
                time="周五晚上9点",
                platform="OKX",
                opinion="ETH这周回调得有点多",
            ),
            _row(
                side="buy",
                coin="DOGE",
                quantity="92个",
                price="0.2174",
                total="20USDT",
                fee="0.092DOGE",
                time="周五晚上9点",
                platform="OKX",
                opinion="DOGE纯属手痒",
            ),
        ),
    ),
    Example(
        "DOT staking pays about 12% a year, so this morning I bought 20 at 4.15 on OKX, "
        "fee 0.02 DOT",
        (
            _row(
                side="buy",
                coin="DOT",
                quantity="20",
                price="4.15",
                fee="0.02 DOT",
                time="this morning",
                platform="OKX",
                opinion="DOT staking pays about 12% a year",
            ),
        ),
    ),
    Example(
        "今天凌晨1点半OKX上再补30U的BTC，单价五万九千八，手续费0.0000005BTC，每周一次的定投，雷打不动",
        (
            _row(
                side="buy",
                coin="BTC",
                price="五万九千八",
                total="30U",
                fee="0.0000005BTC",
                time="今天凌晨1点半",
                platform="OKX",
                opinion="每周一次的定投，雷打不动",
            ),
        ),
    ),
    Example(
        "Bought 3.2 ATOM at 7.84 on OKX yesterday, fee 0.0032 ATOM, a small bet before its upgrade",
        (
            _row(
                side="buy",
                coin="ATOM",
                quantity="3.2 ATOM",
                price="7.84",
                fee="0.0032 ATOM",
                time="yesterday",
                platform="OKX",
                opinion="a small bet before its upgrade",
            ),
        ),
    ),
)

FOURTH_EXAMPLES: tuple[Example, ...] = FIRST_EXAMPLES + ADDED_EXAMPLES
