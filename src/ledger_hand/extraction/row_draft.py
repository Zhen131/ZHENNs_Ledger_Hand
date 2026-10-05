"""One row of the model's table becomes one draft, with the issues it raised.

``draft_from_row`` takes a row as the model wrote it and the surroundings
every row shares (the passage, the coin table, the current moment and the
zone), and gives back a ``RowDraft``: the draft, its issues, and the numbers
of the passage its phrases hold.

Each copied field goes through the same steps:

1. The phrase must be a piece of the passage (``passage``). If it is not,
   the field stays empty and an issue says why. Otherwise the piece, which
   is the passage's own text, is what goes on.
2. The piece is turned into a value with the core's rules:

   - the coin is looked up in the coin table; a coin the table knows goes in
     by its symbol, any other as its name in capitals, a candidate symbol
     that the check of a draft will ask the user to confirm or will refuse;
   - quantity, price, total and fee are read by ``read_number``, which is
     told that the trade's own coin and fee coin, as copied, may stand as a
     unit; nothing else is allowed;
   - the time is read by ``read_time`` with the moment and zone handed in;
   - the pricing currency, the fee's currency, the platform and the opinion
     go in as written.

   A number or time that comes back unsure, unknown, ambiguous, in the
   future or not existing leaves the field empty, with the core's reason in
   an issue. One that comes back with a caution keeps its value, and the
   caution becomes an issue. Two candidate times leave the field empty and
   both go into the issue.
3. A unit that stood with a number is used like this. On the price or the
   total it names the pricing currency: when that field is empty, the unit's
   currency word fills it; when it is not, a unit naming another currency is
   an issue. On the fee it does the same for the fee's currency. On the
   quantity it never goes into the draft, and a unit naming anything other
   than the trade's coin is an issue. A unit naming more than one currency
   is not used, and says so. The unit is the user's own writing, which is
   why using it fills nothing in that the user did not say.

The side is chosen by the model from three words and is taken as it is. The
original text of every draft is the whole passage, unchanged.

Nothing is guessed: a field that none of the above fills stays empty.

Names defined here: ``draft_from_row``, ``RowDraft`` and ``Surroundings``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from ledger_hand.core.coins import CoinTable, spoken_key
from ledger_hand.core.numbers import NotANumber, Recognised, Unsure, read_number
from ledger_hand.core.timeparse import TimeRecognised, TwoCandidates, read_time
from ledger_hand.core.trade import OccurredTime, TradeDraft
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.passage import Passage, Piece, PieceMiss
from ledger_hand.extraction.reply_parser import ReplyRow
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import currencies_in_unit, word_identity

_MISSES = {
    PieceMiss.NOT_IN_PASSAGE: IssueKind.NOT_IN_PASSAGE,
    PieceMiss.CUTS_A_NUMBER: IssueKind.CUTS_A_NUMBER,
}
_NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)


@dataclass(frozen=True)
class Surroundings:
    """What every row of one reply is read against."""

    passage: Passage
    coins: CoinTable
    now: datetime
    zone: str


@dataclass(frozen=True)
class RowDraft:
    """A draft made from one row, its issues, and the passage's numbers its phrases hold."""

    draft: TradeDraft
    issues: tuple[Issue, ...]
    numbers: tuple[str, ...]


@dataclass
class _Row:
    """The work in progress on one row."""

    position: int
    around: Surroundings
    texts: dict[Field, str] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def note(self, kind: IssueKind, at: Field | None = None, **details: object) -> None:
        self.issues.append(Issue(kind=kind, draft=self.position, field=at, **details))  # type: ignore[arg-type]


def draft_from_row(row: ReplyRow, position: int, around: Surroundings) -> RowDraft:
    """The draft that ``row`` makes, as the draft at ``position``."""
    work = _Row(position, around)
    pieces = _pieces(row.cells, work)
    work.texts = {name: piece.text for name, piece in pieces.items()}
    allowed = tuple(
        work.texts[name] for name in (Field.COIN, Field.FEE_CURRENCY) if name in work.texts
    )
    amounts: dict[Field, Decimal | None] = {}
    for name in _NUMBER_FIELDS:
        amounts[name], unit = _number(name, work, allowed)
        if unit is not None:
            _use_unit(name, unit, work, allowed)
    draft = TradeDraft(
        side=row.side,
        coin=_coin(work.texts.get(Field.COIN), around.coins),
        quantity=amounts[Field.QUANTITY],
        price=amounts[Field.PRICE],
        total=amounts[Field.TOTAL],
        quote=work.texts.get(Field.PRICE_CURRENCY),
        fee=amounts[Field.FEE],
        fee_coin=work.texts.get(Field.FEE_CURRENCY),
        occurred=_time(work),
        platform=work.texts.get(Field.PLATFORM),
        note=work.texts.get(Field.OPINION),
        raw_text=around.passage.text,
    )
    numbers = tuple(number for piece in pieces.values() for number in piece.numbers)
    return RowDraft(draft, tuple(work.issues), numbers)


def _pieces(cells: Mapping[Field, str], work: _Row) -> dict[Field, Piece]:
    """The pieces of the passage the row's phrases are; each phrase that is not one is noted."""
    pieces: dict[Field, Piece] = {}
    for name, phrase in cells.items():
        found = work.around.passage.find(phrase)
        if isinstance(found, PieceMiss):
            work.note(_MISSES[found], name, phrase=phrase)
        else:
            pieces[name] = found
    return pieces


def _coin(text: str | None, coins: CoinTable) -> str | None:
    if text is None:
        return None
    coin = coins.find(text)
    return coin.symbol if coin is not None else spoken_key(text)


def _number(name: Field, work: _Row, allowed: tuple[str, ...]) -> tuple[Decimal | None, str | None]:
    """The value of a number field and the unit that stood with it, or nothing."""
    text = work.texts.get(name)
    if text is None:
        return None, None
    reading = read_number(text, extra_units=allowed)
    if isinstance(reading, Recognised):
        for caution in reading.cautions:
            work.note(IssueKind.NUMBER_CAUTION, name, phrase=text, cause=caution)
        return reading.value, reading.unit
    if isinstance(reading, Unsure):
        work.note(IssueKind.NUMBER_UNSURE, name, phrase=text, cause=reading.reason)
    elif isinstance(reading, NotANumber):
        work.note(IssueKind.NOT_A_NUMBER, name, phrase=text)
    return None, None


# Which field a unit on each number field speaks for, and the issue when it
# names another currency than that field.
_UNIT_TARGETS = {
    Field.PRICE: (Field.PRICE_CURRENCY, IssueKind.UNIT_NOT_THE_PRICE_CURRENCY),
    Field.TOTAL: (Field.PRICE_CURRENCY, IssueKind.UNIT_NOT_THE_PRICE_CURRENCY),
    Field.FEE: (Field.FEE_CURRENCY, IssueKind.UNIT_NOT_THE_FEE_CURRENCY),
    Field.QUANTITY: (Field.COIN, IssueKind.UNIT_NOT_THE_COIN),
}


def _use_unit(name: Field, unit: str, work: _Row, allowed: tuple[str, ...]) -> None:
    coins = work.around.coins
    named = currencies_in_unit(unit, coins, allowed)
    if not named:
        return
    target, mismatch = _UNIT_TARGETS[name]
    if name is not Field.QUANTITY and len(named) > 1:
        work.note(IssueKind.UNIT_NAMES_SEVERAL, name, phrase=unit)
        return
    current = work.texts.get(target)
    if current is None and name is not Field.QUANTITY:
        work.texts[target] = named[0].text
        return
    wanted = None if current is None else word_identity(current, coins)
    if any(word.identity != wanted for word in named):
        work.note(mismatch, name, phrase=unit)


def _time(work: _Row) -> OccurredTime | None:
    text = work.texts.get(Field.TIME)
    if text is None:
        return None
    reading = read_time(text, work.around.now, work.around.zone)
    if isinstance(reading, TimeRecognised):
        for caution in reading.cautions:
            work.note(IssueKind.TIME_CAUTION, Field.TIME, phrase=text, cause=caution)
        return reading.time
    if isinstance(reading, TwoCandidates):
        candidates = (reading.earlier, reading.later)
        work.note(IssueKind.TWO_TIMES, Field.TIME, phrase=text, candidates=candidates)
        for caution in reading.cautions:
            work.note(IssueKind.TIME_CAUTION, Field.TIME, phrase=text, cause=caution)
        return None
    work.note(IssueKind.TIME_REFUSED, Field.TIME, phrase=text, cause=reading.reason)
    return None
