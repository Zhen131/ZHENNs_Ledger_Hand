"""Asking the price of one unit in the asset's own money, for a trade paid in another money.

"花了128欧元买了2股KO，换汇费0.19欧元", with KO priced in US dollars: the
ledger needs the rate between the two moneys, which is worked out from the
price of one share in US dollars, and that was not said. The program asks
for it in a fixed sentence of its own (the model words no part of it):

    [Trade 1 of 1: price in USD] Trade 1 was paid in EUR, but KO is
    priced in USD. How much was one share in USD?

The answer is read by the program, never by the model
(``read_said_price``):

- "skip" or "cancel" (and their other words) as for every question;
- one number above 0 with no money beside it ("69.5"): the question names
  the money, so it is that price;
- one number with the asset's own money named ("69.5美元", "69.5 USD"):
  the same;
- a number with a vague word ("69.5美金"), the money paid, or any other
  money ("69.5 USDT"): the question is asked again, saying what was
  answered, since USDT and the US dollar never stand for each other;
- anything else: asked again, saying it could not be read.

Names defined here: ``said_price_question``, ``SaidPriceAnswer`` and
``read_said_price``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.asking.question_text import Writer
from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.followup import AskSaidPrice
from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.extraction.answer_phrase import Command
from ledger_hand.extraction.answer_words import CANCEL_WORDS, SKIP_WORDS, tidy
from ledger_hand.extraction.unit_currency import currencies_in_unit
from ledger_hand.flows.progress import Question
from ledger_hand.flows.questions import SKIP_OR_CANCEL

# The program's sentence; the keyword a test looks for is "in {money}?".
_SENTENCE = (
    "Trade {number} was paid in {paid}, but {asset} is priced in {money}. "
    "How much was one {unit} in {money}?"
)
_LABEL = "[Trade {number} of {of}: price in {money}]"
_ANSWER_NOTE = "Answer with the price of one {unit} in {money}, such as '69.5'."


def said_price_question(
    position: int, trades: int, asked: AskSaidPrice, again: str | None = None
) -> Question:
    """The question about trade ``position`` (from 0) of ``trades``; ``again`` says why it is
    asked again."""
    number = position + 1
    words = {
        "number": number,
        "of": trades,
        "paid": asked.paid,
        "asset": asked.asset,
        "money": asked.money,
        "unit": asked.unit,
    }
    return Question(
        trade=position,
        asked=asked,
        label=_LABEL.format(**words),
        sentence=_SENTENCE.format(**words),
        writer=Writer.PROGRAM,
        notes=(_ANSWER_NOTE.format(**words), SKIP_OR_CANCEL),
        again=again,
    )


@dataclass(frozen=True)
class SaidPriceAnswer:
    """What an answer says: a price in the asset's own money, a command, or why it was not used.

    Exactly one of the three is there.
    """

    price: Decimal | None = None
    command: Command | None = None
    not_used: str | None = None


def read_said_price(text: str, asked: AskSaidPrice, assets: AssetTable) -> SaidPriceAnswer:
    """What ``text`` says about the price asked, by the rules above.

    Example: "69.5" gives 69.5; "69.5美金" is not used, since "美金" may
    be USDT or the US dollar.
    """
    tidied = tidy(text)
    if not tidied:
        return SaidPriceAnswer(not_used="nothing was answered")
    if tidied in SKIP_WORDS:
        return SaidPriceAnswer(command=Command.SKIP)
    if tidied in CANCEL_WORDS:
        return SaidPriceAnswer(command=Command.CANCEL)
    reading = read_number(text.strip(), extra_units=(*assets.money_units, *assets.extra_units))
    if not isinstance(reading, Recognised) or reading.value <= 0:
        return SaidPriceAnswer(
            not_used=f"{text.strip()!r} could not be read as one price above 0 in {asked.money}"
        )
    unit = reading.unit
    if unit is None:
        return SaidPriceAnswer(price=reading.value)
    named = [word.text for word in currencies_in_unit(unit, assets)]
    if not named:
        return SaidPriceAnswer(price=reading.value)
    found = assets.money(named[0]) if len(named) == 1 else None
    if found is not None and found.reading is MoneyReading.ONE and found.code == asked.money:
        return SaidPriceAnswer(price=reading.value)
    if found is not None and found.reading is MoneyReading.VAGUE:
        why = f"{named[0]!r} may mean USDT or the US dollar"
    else:
        why = f"{unit!r} is not {asked.money}"
    return SaidPriceAnswer(
        not_used=f"you said {text.strip()!r}, and {why}; say the price in {asked.money}"
    )
