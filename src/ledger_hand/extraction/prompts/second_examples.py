"""The examples of the second prompt version: the first prompt's ten, then six in the owner's way.

``SECOND_EXAMPLES`` is the first prompt's examples, the very same objects in
the same order, followed by ``OWNER_EXAMPLES``. Every passage and every
trade of these six is invented, and so is every opinion in them; none is
copied from a real trade or from a test sentence. They are written the way
the owner writes about a trade: no space between Chinese and a number, buys
only, on OKX, the fee paid in the coin bought, 20 to 100 USDT a trade.

Between them they show:

- an amount with U right after it that is the total, with no quantity said
  ("又补了40U", "再补50U", "35U买了点XRP");
- a long opinion of several clauses, with a price or a percentage in it that
  is not the trade's price, said before the trade or after it, copied whole
  but without the mark that sets it apart from the trade;
- a quantity, a price and a fee written right against the Chinese
  ("成交60.24个", "0.83一个", "手续费0.06024ARB");
- 买到, 买了点, 补仓 and a limit order that was filled, each a buy;
- two trades in one passage that share the time and the exchange, each with
  an opinion of its own in its own part of the passage.

In every row, each field is copied from its passage character for
character, or is left out because the passage does not say it; a currency
written next to a number is not copied again into a field of its own.

Names defined here: ``SECOND_EXAMPLES`` and ``OWNER_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


OWNER_EXAMPLES: tuple[Example, ...] = (
    Example(
        "昨晚22:50在OKX又补了40U的SOL，142.6一个，手续费0.00028SOL。"
        "SOL这个月已经回调了-18%，越跌越想多攒一点，等反弹再说",
        (
            _row(
                side="buy",
                coin="SOL",
                price="142.6",
                total="40U",
                fee="0.00028SOL",
                time="昨晚22:50",
                platform="OKX",
                opinion="SOL这个月已经回调了-18%，越跌越想多攒一点，等反弹再说",
            ),
        ),
    ),
    Example(
        "夜里睡不着看了眼行情，LINK从16一路跌到12出头，感觉已经跌出性价比了。"
        "今天凌晨1点10分在OKX补仓，50USDT成交4.0485个LINK，均价12.35，手续费0.0040485LINK；"
        "AVAX生态最近挺热闹，先拿小钱试试水，30USDT买了1.2096个，24.8一个，手续费0.0012096AVAX",
        (
            _row(
                side="buy",
                coin="LINK",
                quantity="4.0485个LINK",
                price="12.35",
                total="50USDT",
                fee="0.0040485LINK",
                time="今天凌晨1点10分",
                platform="OKX",
                opinion="夜里睡不着看了眼行情，LINK从16一路跌到12出头，感觉已经跌出性价比了",
            ),
            _row(
                side="buy",
                coin="AVAX",
                quantity="1.2096个",
                price="24.8",
                total="30USDT",
                fee="0.0012096AVAX",
                time="今天凌晨1点10分",
                platform="OKX",
                opinion="AVAX生态最近挺热闹，先拿小钱试试水",
            ),
        ),
    ),
    Example(
        "刚才在OKX用35U买了点XRP，0.5821一个，手续费0.0601XRP，它一直在0.6下面磨，等不及了",
        (
            _row(
                side="buy",
                coin="XRP",
                price="0.5821",
                total="35U",
                fee="0.0601XRP",
                time="刚才",
                platform="OKX",
                opinion="它一直在0.6下面磨，等不及了",
            ),
        ),
    ),
    Example(
        "前天下午5点再补50U的ARB，OKX成交60.24个，0.83一个，手续费0.06024ARB，这次是分批建仓的第三笔",
        (
            _row(
                side="buy",
                coin="ARB",
                quantity="60.24个",
                price="0.83",
                total="50U",
                fee="0.06024ARB",
                time="前天下午5点",
                platform="OKX",
                opinion="这次是分批建仓的第三笔",
            ),
        ),
    ),
    Example(
        "LTC在66附近反复站稳，前几天就挂了限价单等着。"
        "今晚9点半触发后成交，OKX显示买到0.75个，均价66.2，共49.65USDT，手续费0.00075LTC",
        (
            _row(
                side="buy",
                coin="LTC",
                quantity="0.75个",
                price="66.2",
                total="49.65USDT",
                fee="0.00075LTC",
                time="今晚9点半",
                platform="OKX",
                opinion="LTC在66附近反复站稳，前几天就挂了限价单等着",
            ),
        ),
    ),
    Example(
        "今天早上8点在OKX分两笔买的：DOT跌到4块以下了，先拿40USDT买到10.25个，均价3.9，"
        "手续费0.01025DOT；ATOM最近被朋友念叨了好几次，也买了4.5个，4.44一个，花了20USDT，"
        "手续费0.0045ATOM",
        (
            _row(
                side="buy",
                coin="DOT",
                quantity="10.25个",
                price="3.9",
                total="40USDT",
                fee="0.01025DOT",
                time="今天早上8点",
                platform="OKX",
                opinion="DOT跌到4块以下了",
            ),
            _row(
                side="buy",
                coin="ATOM",
                quantity="4.5个",
                price="4.44",
                total="20USDT",
                fee="0.0045ATOM",
                time="今天早上8点",
                platform="OKX",
                opinion="ATOM最近被朋友念叨了好几次",
            ),
        ),
    ),
)

SECOND_EXAMPLES: tuple[Example, ...] = FIRST_EXAMPLES + OWNER_EXAMPLES
