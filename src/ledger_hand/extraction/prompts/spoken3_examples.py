"""The examples the third version for Chinese adds: the second one's, and one more.

Every passage and every trade here is invented, and the prices are made up.
The passage is written as the program hands it to the model, already
tidied. It holds both the person's own view of the trade ("感觉还能涨"),
which is the opinion, and a remark about another coin that day, which is
not. Every field is copied from its passage character for character, gaps
and all, or left out.

Names defined here: ``SPOKEN_EXAMPLES_3`` and ``SPOKEN_3_EXAMPLES``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompting import Example, ExampleRow
from ledger_hand.extraction.prompts.spoken2_examples import SPOKEN_2_EXAMPLES
from ledger_hand.extraction.reply_table import Field


def _row(**cells: str) -> ExampleRow:
    """A row from field names written as keywords; a field not given is empty."""
    return {Field(name): text for name, text in cells.items()}


SPOKEN_EXAMPLES_3: tuple[Example, ...] = (
    Example(
        "2026年8月25号上午10点08分在OKX买了30个SOL，均价148.6U，手续费是0.15个SOL，感觉还能涨，那天以太跌了不少。",
        (
            _row(
                side="buy",
                coin="SOL",
                quantity="30个SOL",
                price="148.6U",
                fee="0.15个SOL",
                time="2026年8月25号上午10点08分",
                platform="OKX",
                opinion="感觉还能涨",
            ),
        ),
    ),
)

SPOKEN_3_EXAMPLES: tuple[Example, ...] = (*SPOKEN_2_EXAMPLES, *SPOKEN_EXAMPLES_3)
