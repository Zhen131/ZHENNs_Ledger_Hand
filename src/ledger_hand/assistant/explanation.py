"""Whether the model's words after a lookup may reach the user, or give way to the program's.

After a read tool, the program lays the table out itself (``lookups``), and
the model only writes a sentence or two beside it. Those words are checked
before the user sees them (``check_explanation``):

- What counts as a number: every run of Arabic digits, with its decimal
  point and its thousands commas ("61,940", "0.0081", "10"). Chinese
  numerals ("一共", "两笔") do not count.
- What it is checked against: the numbers in what was handed to the model
  for this turn, in the header and table the user is shown (the days, the
  count, each row's time among them) and in what the user just said. A
  date counts as its parts: "2026-10-06" gives 2026, 10 and 6.
- How: by value, with the thousands commas taken out, so "61,940" is
  61940 and "1000.50" is 1000.5; "281.39" is not 281.394. A sign before a
  number is not looked at.

One number not found, or words longer than ``LONGEST_EXPLANATION``, and the
model's words are not used: the user is told ``AFTER_A_TABLE`` instead, and
the reason is kept for the record.

Without any lookup in the turn, the model's answer may hold no figure that
looks like an amount (``check_plain_answer``): a run of digits with a
decimal point, or with three digits or more ("61000", "0.5", "2026"), is
held to be one, and the answer gives way to ``NO_TABLE``. "你可以问我 10 月
的交易" passes. This errs on the side of turning good words away.

Names defined here: ``LONGEST_EXPLANATION``, ``AFTER_A_TABLE``, ``NO_TABLE``,
``Withheld``, ``numbers_in``, ``check_explanation`` and ``check_plain_answer``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# One or two sentences in either language fit well within this many
# characters. This is a guess, to be checked against real explanations.
LONGEST_EXPLANATION = 300

AFTER_A_TABLE = "Here is what the ledger returned."
NO_TABLE = (
    "I can only answer from your ledger: your trades, the sums of a stretch of time, "
    "what you hold now, and the assets it knows. Please ask about one of those."
)

# Full-width digits and point, read as ordinary ones; nothing else is changed.
_DIGITS = str.maketrans({chr(0xFF10 + digit): str(digit) for digit in range(10)} | {"．": "."})
_NUMBER = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+(?![0-9])(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?")


@dataclass(frozen=True)
class Withheld:
    """The model's words were not used, and why, in one sentence for the record."""

    reason: str


def numbers_in(text: str) -> tuple[str, ...]:
    """Every number written in Arabic digits in ``text``, as written."""
    return tuple(_NUMBER.findall(text.translate(_DIGITS)))


def _value(number: str) -> Decimal | None:
    try:
        return Decimal(number.replace(",", ""))
    except InvalidOperation:
        return None


def check_explanation(words: str, checked_against: Iterable[str]) -> Withheld | None:
    """``None`` when ``words`` may be shown beside the table; else why not."""
    if len(words) > LONGEST_EXPLANATION:
        return Withheld(f"longer than {LONGEST_EXPLANATION} characters")
    allowed = {
        value
        for text in checked_against
        for number in numbers_in(text)
        if (value := _value(number)) is not None
    }
    for number in numbers_in(words):
        if _value(number) not in allowed:
            return Withheld(f"{number} is not in what the ledger returned")
    return None


def check_plain_answer(words: str) -> Withheld | None:
    """``None`` when an answer without a lookup holds no figure like an amount; else why."""
    for number in numbers_in(words):
        if "." in number or sum(character.isdigit() for character in number) >= 3:
            return Withheld(f"{number} looks like an amount, and nothing was looked up")
    return None
