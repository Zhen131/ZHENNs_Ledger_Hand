"""One field of one trade: is the draft's value the gold one, and if not, what kind of wrong.

Eleven fields are scored: side, coin, quantity, price, total, pricing
currency, fee, fee currency, time, platform and opinion. The original text
is not scored: every draft holds the whole passage.

Both sides are put in the same form before they are compared:

- a coin or currency is compared by what it names (``BTC`` and 比特币 are
  both BTC; U, 刀 and USDT are all USDT), the way the program itself tells
  currencies apart (``unit_currency.word_identity``);
- a number by its value, not its writing (1200.0 is 1200);
- a time by its precision and the instant or day it names;
- a platform or opinion as text, after the same tidying on both sides:
  full-width characters taken as their ordinary width, runs of whitespace
  as one space, whitespace at either end left out.

``judge_cell`` sorts every field into exactly one ``CellOutcome``:

- ``RIGHT``: the draft holds the gold value, or both are empty;
- ``LEFT_EMPTY_WITH_REASON``: the gold value is not empty, the draft's is,
  and the issues say why (``EmptyReason``);
- ``LEFT_EMPTY_BY_MODEL``: the same, but no issue is about the field: the
  model copied nothing that gives it;
- ``WRONG_WITH_ISSUE``: the draft holds another value, and an issue is
  about the field (a caution, a unit that does not fit);
- ``WRONG_SILENT``: the draft holds another value, and no issue is about
  the field;
- ``MADE_UP``: the gold value is empty and the draft holds one.

An issue is about a field when it names the same draft and the field, or a
field whose unit fills it: the price and the total for the pricing
currency, the fee for the fee currency, and the quantity's unit for the
coin.

A cell is also marked a half copy when the model's phrase for it is a
shorter piece of the gold phrase and the field did not come out right:
the model copied part of what the person wrote ("900" of "94 900", "3" of
"3 w"), whether the program then caught it or not.

Names defined here: ``CellOutcome``, ``EmptyReason``, ``CellResult``,
``judge_cell``, ``agrees``, ``shown``, ``tidy_text``, ``SCORED_FIELDS``
and ``COPIED_SCORED_FIELDS``.
"""

from __future__ import annotations

import enum
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from evals.gold import GoldCell, GoldValue
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.numbers import write_number
from ledger_hand.core.timeparse import write_time
from ledger_hand.core.trade import OccurredTime, Side, TradeDraft
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import word_identity

SCORED_FIELDS: tuple[Field, ...] = tuple(Field)
COPIED_SCORED_FIELDS: tuple[Field, ...] = tuple(f for f in Field if f is not Field.SIDE)


class CellOutcome(enum.Enum):
    """What came of one field, compared with the gold answer."""

    RIGHT = "right"
    LEFT_EMPTY_WITH_REASON = "left empty by the program, with the reason in the issues"
    LEFT_EMPTY_BY_MODEL = "left empty, with no issue: the model copied nothing that gives it"
    WRONG_WITH_ISSUE = "a wrong value in the draft, with an issue about the field"
    WRONG_SILENT = "a wrong value in the draft, with no issue about the field"
    MADE_UP = "a value in the draft where the gold answer is empty"


class EmptyReason(enum.Enum):
    """Why the program left a field empty, from the issue about it."""

    NOT_IN_PASSAGE = "the model's phrase is not a piece of the passage"
    CUTS_A_NUMBER = "the model's phrase cuts a number of the passage"
    NUMBER_NOT_READ = "the number reader was unsure of the phrase or could not read it"
    TIME_NOT_READ = "the time reader refused the phrase or gave two candidates"
    OTHER = "another issue about the field"


_REASON_OF_KIND = {
    IssueKind.NOT_IN_PASSAGE: EmptyReason.NOT_IN_PASSAGE,
    IssueKind.CUTS_A_NUMBER: EmptyReason.CUTS_A_NUMBER,
    IssueKind.NUMBER_UNSURE: EmptyReason.NUMBER_NOT_READ,
    IssueKind.NOT_A_NUMBER: EmptyReason.NUMBER_NOT_READ,
    IssueKind.TIME_REFUSED: EmptyReason.TIME_NOT_READ,
    IssueKind.TWO_TIMES: EmptyReason.TIME_NOT_READ,
}

# The fields whose issues are also about a field: a unit on a number fills a
# currency or speaks for the coin.
_ALSO_ABOUT: Mapping[Field, frozenset[Field]] = {
    Field.PRICE_CURRENCY: frozenset({Field.PRICE, Field.TOTAL}),
    Field.FEE_CURRENCY: frozenset({Field.FEE}),
}
_COIN_UNIT_KIND = IssueKind.UNIT_NOT_THE_COIN

_DRAFT_ATTRIBUTE = {
    Field.SIDE: "side",
    Field.COIN: "coin",
    Field.QUANTITY: "quantity",
    Field.PRICE: "price",
    Field.TOTAL: "total",
    Field.PRICE_CURRENCY: "quote",
    Field.FEE: "fee",
    Field.FEE_CURRENCY: "fee_coin",
    Field.TIME: "occurred",
    Field.PLATFORM: "platform",
    Field.OPINION: "note",
}
_WORD_FIELDS = frozenset({Field.COIN, Field.PRICE_CURRENCY, Field.FEE_CURRENCY})
_TEXT_FIELDS = frozenset({Field.PLATFORM, Field.OPINION})


@dataclass(frozen=True)
class CellResult:
    """What came of one field: the outcome, and what was compared.

    ``gold`` and ``got`` are the two values as text (``None`` when empty);
    ``copied`` is the phrase the model wrote for the field, if any.
    ``reason`` is set only for ``LEFT_EMPTY_WITH_REASON``. ``issues`` are the
    kinds of the issues about the field.
    """

    field: Field
    outcome: CellOutcome
    gold: str | None
    got: str | None
    copied: str | None
    half_copy: bool
    reason: EmptyReason | None = None
    issues: tuple[IssueKind, ...] = ()


def draft_value(draft: TradeDraft, field: Field) -> GoldValue | None:
    """The value ``draft`` holds in ``field``."""
    value = getattr(draft, _DRAFT_ATTRIBUTE[field])
    return value if isinstance(value, Side | str | Decimal | OccurredTime) else None


def agrees(field: Field, gold: GoldValue | None, got: GoldValue | None) -> bool:
    """Whether ``got`` is the gold value of ``field``, both put in the same form."""
    if gold is None or got is None:
        return gold is None and got is None
    if field in _WORD_FIELDS:
        return _identity(gold) == _identity(got)
    if field in _TEXT_FIELDS:
        return tidy_text(str(gold)) == tidy_text(str(got))
    if isinstance(gold, OccurredTime) and isinstance(got, OccurredTime):
        return _same_time(gold, got)
    if isinstance(gold, Decimal) and isinstance(got, Decimal):
        return gold == got
    return gold == got


def _identity(word: object) -> str:
    return word_identity(str(word), BUILT_IN_TABLE)


def _same_time(gold: OccurredTime, got: OccurredTime) -> bool:
    if gold.precision is not got.precision or gold.time_zone != got.time_zone:
        return False
    if isinstance(gold.value, datetime) and isinstance(got.value, datetime):
        return gold.value == got.value
    if isinstance(gold.value, datetime) or isinstance(got.value, datetime):
        return False
    return gold.value == got.value


def _width_pairs() -> dict[int, int]:
    """Characters Unicode marks as another width of one other character, and that character."""
    pairs: dict[int, int] = {}
    for code in (0x3000, *range(0xFF00, 0xFFF0)):
        tag, _, target = unicodedata.decomposition(chr(code)).partition(" ")
        if tag in ("<wide>", "<narrow>") and target and " " not in target:
            pairs[code] = int(target, 16)
    return pairs


_OTHER_WIDTH = _width_pairs()


def tidy_text(text: str) -> str:
    """``text`` in ordinary width, runs of whitespace as one space, ends trimmed."""
    return " ".join(text.translate(_OTHER_WIDTH).split())


def shown(value: GoldValue | None) -> str | None:
    """A value as text, for the results file and the examples."""
    if value is None:
        return None
    if isinstance(value, Side):
        return value.value
    if isinstance(value, Decimal):
        return write_number(value)
    if isinstance(value, OccurredTime):
        return f"{write_time(value)} ({value.precision.value})"
    return value


def issues_about(field: Field, position: int, issues: Iterable[Issue]) -> tuple[Issue, ...]:
    """The issues about ``field`` of the draft at ``position``."""
    also = _ALSO_ABOUT.get(field, frozenset())
    found: list[Issue] = []
    for issue in issues:
        if issue.draft != position or issue.field is None:
            continue
        if (
            issue.field is field
            or issue.field in also
            or field is Field.COIN
            and issue.kind is _COIN_UNIT_KIND
        ):
            found.append(issue)
    return tuple(found)


def judge_cell(
    field: Field,
    gold: GoldCell,
    got: GoldValue | None,
    about: tuple[Issue, ...],
    copied: str | None,
) -> CellResult:
    """The outcome of ``field``: gold cell ``gold``, the draft's value ``got``.

    ``about`` are the issues about the field; ``copied`` is the model's phrase.
    """
    outcome, reason = _outcome(field, gold.value, got, about)
    half = outcome is not CellOutcome.RIGHT and _is_part(copied, gold.phrase)
    return CellResult(
        field=field,
        outcome=outcome,
        gold=shown(gold.value),
        got=shown(got),
        copied=copied,
        half_copy=half,
        reason=reason,
        issues=tuple(issue.kind for issue in about),
    )


def _outcome(
    field: Field, gold: GoldValue | None, got: GoldValue | None, about: tuple[Issue, ...]
) -> tuple[CellOutcome, EmptyReason | None]:
    if agrees(field, gold, got):
        return CellOutcome.RIGHT, None
    if gold is None:
        return CellOutcome.MADE_UP, None
    if got is None:
        if not about:
            return CellOutcome.LEFT_EMPTY_BY_MODEL, None
        return CellOutcome.LEFT_EMPTY_WITH_REASON, _reason(about)
    if about:
        return CellOutcome.WRONG_WITH_ISSUE, None
    return CellOutcome.WRONG_SILENT, None


def _reason(about: tuple[Issue, ...]) -> EmptyReason:
    for issue in about:
        if issue.kind in _REASON_OF_KIND:
            return _REASON_OF_KIND[issue.kind]
    return EmptyReason.OTHER


def _is_part(copied: str | None, phrase: str | None) -> bool:
    """Whether ``copied`` is a shorter piece of ``phrase``, after tidying both."""
    if copied is None or phrase is None:
        return False
    part, whole = tidy_text(copied), tidy_text(phrase)
    return bool(part) and part != whole and part in whole
