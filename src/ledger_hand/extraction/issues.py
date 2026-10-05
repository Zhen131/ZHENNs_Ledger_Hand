"""The list of issues that comes with the drafts: what was left empty, and what to look at.

Extraction never fills a field it is not sure of. Every field it leaves empty
for a reason, every value it keeps with a caution, and every row it leaves
out, is one ``Issue`` in the list that comes back with the drafts. So are
the numbers of the passage that no trade used, since they may belong to a
trade the model missed.

An issue says what kind it is, which draft and field it is about where it is
about one, the phrase or unit it is about as written, and the core's own
reason where the core gave one. What to ask the user, and how, is decided
later; this module only states the shapes.

Names defined here: ``Issue``, ``IssueKind`` and ``Cause``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ledger_hand.core.numbers import Caution, Doubt
from ledger_hand.core.timeparse import Refusal, TimeCaution
from ledger_hand.core.trade import OccurredTime
from ledger_hand.extraction.reply_table import Field


class IssueKind(enum.Enum):
    """What an issue is about; the value says it in words."""

    NOT_IN_PASSAGE = "the model wrote a phrase that is not a piece of the passage; left empty"
    CUTS_A_NUMBER = "the model copied part of a longer number in the passage; left empty"
    NUMBER_UNSURE = "the phrase cannot be pinned to one number; left empty"
    NOT_A_NUMBER = "the phrase is not a number this program reads; left empty"
    NUMBER_CAUTION = "the number was read and kept, with a caution"
    TIME_REFUSED = "the phrase was not turned into a time; left empty"
    TWO_TIMES = "the clocks showed this time twice that day; left empty until one is chosen"
    TIME_CAUTION = "the time was read and kept, with a caution"
    UNIT_NOT_THE_COIN = "the quantity carries a unit that is not the trade's coin"
    UNIT_NOT_THE_PRICE_CURRENCY = (
        "the price or total carries a unit other than the pricing currency"
    )
    UNIT_NOT_THE_FEE_CURRENCY = "the fee carries a unit other than the currency of the fee"
    UNIT_NAMES_SEVERAL = "the unit names more than one currency, so it is not used"
    EMPTY_ROW = "the model gave a row with every field empty; it was left out"
    SAME_AS_ANOTHER = "the model gave the same row twice; the passage may mention it only once"
    NUMBERS_LEFT_OVER = "numbers in the passage that no trade used; a trade may be missing"


type Cause = Doubt | Caution | Refusal | TimeCaution
"""The core's own reason, where it gave one."""


@dataclass(frozen=True, kw_only=True)
class Issue:
    """One thing about the drafts to look at.

    ``draft`` is the position of the draft it is about, counting from 0, or
    ``None`` when it is about the passage or a row that was left out.
    ``field`` is the field it is about, if one. ``phrase`` is what it is
    about as written: the phrase the model wrote, or the unit that stood
    with a number. ``cause`` is the core's reason. ``candidates`` are the two
    moments a time may be. ``numbers`` are the numbers no trade used, as the
    passage writes them. ``same_as`` is the position of the earlier draft a
    repeated row repeats.
    """

    kind: IssueKind
    draft: int | None = None
    field: Field | None = None
    phrase: str | None = None
    cause: Cause | None = None
    candidates: tuple[OccurredTime, ...] = ()
    numbers: tuple[str, ...] = ()
    same_as: int | None = None
