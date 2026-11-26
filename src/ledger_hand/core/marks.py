"""The marks on the cells of a trade sent: worked out, assumed, or suspicious with a reason.

A mark tells the person, before they confirm a trade, which cell they did
not say themselves: the program worked it out from the others
(``MarkKind.COMPUTED``), assumed it (``MarkKind.INFERRED``), or thinks it
is probably wrong (``MarkKind.SUSPICIOUS``, always with a reason). The
kinds and the cells' names are the ledger's own words for them
(``assistant-link/README.md`` in the ledger, "Unfinished trades and field
marks"), so a mark can be handed to it as it is.

The ledger's rules for marks hold here from the moment one is made: one
mark a cell; a suspicious mark has a reason that is not blank; a reason is
at most ``REASON_MOST`` units long, counted as the ledger counts, in
UTF-16 units (an emoji counts two); an empty cell can only be suspicious.
``cut_reason`` shortens a reason to fit, ending it with "…", and never
splits a character in two.

``marks_for`` works out every mark of one trade from its record, the
comparison of its price with the market price (``price_check``) and the
ledger's name of an asset the model matched. It asks nothing and reads no
clock. Which cell gets which mark:

- worked out: the amount the program calculated (``TradeRecord.derived``);
- assumed: the money guessed from the ledger's last trade of the asset
  (``TradeRecord.inferred``), and the asset the model matched to the
  user's words from the ledger's list (``TradeRecord.picked``);
- suspicious: the price, when it is far from the market price.

When one cell earns two marks, the one kept is suspicious before assumed
before worked out, and the reason of the one dropped is put first in the
reason kept. A time zone, a year or "today" the program filled in is not
marked: nearly every trade has one, and marking them all would leave the
marks unread (decided by the contract's author, 2026-11-25).

``as_sent`` is the guard before marks leave for the ledger: a cell sent
empty, or not at all, keeps only a suspicious mark, the time of day and
the time zone keep none when they are not sent, and each mark is the
three keys the ledger takes.

Names defined here: ``MarkKind``, ``Field``, ``REASON_MOST``,
``reason_length``, ``cut_reason``, ``FieldMark``, ``TradeMarks``,
``FAR_REASON_START``, ``marks_for``, ``far_reason``, ``fields_sent`` and
``as_sent``.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.ledger_limits import text_length
from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.price_check import PriceCheck, PriceVerdict
from ledger_hand.core.trade import Amount, Inferred, InferredFrom, TradeRecord

# The ledger's FIELD_MARK_REASON_MAX_LENGTH, counted in UTF-16 units as the
# ledger's JavaScript counts a string's length (2026-11-25).
REASON_MOST = 256

_ELLIPSIS = "…"
_JOIN = "; "

# The start of every reason that says a price is far from the market price.
FAR_REASON_START = "far from the market price"


class MarkKind(enum.Enum):
    """What a mark says about a cell; the value is the ledger's word for it."""

    COMPUTED = "computed"
    """The program worked it out from the other cells."""
    INFERRED = "inferred"
    """The program assumed it; the user did not say it."""
    SUSPICIOUS = "suspicious"
    """The program thinks it is probably wrong, and says why."""


class Field(enum.Enum):
    """A cell of a trade that can carry a mark; the value is the ledger's name for it."""

    OCCURRED_DATE = "occurredDate"
    OCCURRED_TIME = "occurredTime"
    OCCURRED_TIME_ZONE = "occurredTimeZone"
    TYPE = "type"
    ASSET_ID = "assetId"
    QUANTITY = "quantity"
    PRICE = "price"
    TOTAL_VALUE = "totalValue"
    QUOTE_ASSET_ID = "quoteAssetId"
    FEE = "fee"
    FEE_ASSET_ID = "feeAssetId"
    COST_RATE = "costRate"
    PLATFORM = "platform"
    NOTE = "note"


# Which mark is kept when one cell earns two: the earlier in this order.
_KEPT_FIRST = (MarkKind.SUSPICIOUS, MarkKind.INFERRED, MarkKind.COMPUTED)

# The cells of the time; neither is marked when only the day is sent.
_TIME_OF_DAY = frozenset({Field.OCCURRED_TIME, Field.OCCURRED_TIME_ZONE})


def reason_length(text: str) -> int:
    """How long ``text`` is as the ledger counts it: UTF-16 units. "😀" counts 2."""
    return text_length(text)


def cut_reason(text: str, most: int = REASON_MOST) -> str:
    """``text`` cut to at most ``most`` UTF-16 units, ending with "…" when it was cut.

    A character is never split: one that takes two units goes whole or not
    at all. Example: 300 letters become 255 letters and "…".
    """
    if reason_length(text) <= most:
        return text
    room = most - reason_length(_ELLIPSIS)
    kept: list[str] = []
    used = 0
    for character in text:
        size = reason_length(character)
        if used + size > room:
            break
        kept.append(character)
        used += size
    return "".join(kept) + _ELLIPSIS


@dataclass(frozen=True)
class FieldMark:
    """One mark on one cell: which cell, which kind, and why (a suspicious one always says)."""

    field: Field
    kind: MarkKind
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field, Field) or not isinstance(self.kind, MarkKind):
            raise TypeError("a mark names a Field and a MarkKind")
        reason = self.reason
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError("a mark's reason is text that is not blank, or none")
        if self.kind is MarkKind.SUSPICIOUS and self.reason is None:
            raise ValueError("a suspicious mark says why")
        if self.reason is not None and reason_length(self.reason) > REASON_MOST:
            raise ValueError(f"a mark's reason is at most {REASON_MOST} UTF-16 units long")


@dataclass(frozen=True)
class TradeMarks:
    """Every mark of one trade, and the cells sent empty (none until empty cells are sent).

    One mark a cell; an empty cell carries a suspicious mark or none.
    """

    marks: tuple[FieldMark, ...] = ()
    empty: frozenset[Field] = frozenset()

    def __post_init__(self) -> None:
        fields = [mark.field for mark in self.marks]
        if len(set(fields)) != len(fields):
            raise ValueError("a cell carries one mark at most")
        for mark in self.marks:
            if mark.field in self.empty and mark.kind is not MarkKind.SUSPICIOUS:
                raise ValueError(f"the empty cell {mark.field.value} can only be suspicious")

    def on(self, field: Field) -> FieldMark | None:
        """The mark on ``field``, or ``None``."""
        return next((mark for mark in self.marks if mark.field is field), None)


# --- working the marks out -------------------------------------------------------

_WORKED_OUT = {
    Amount.QUANTITY: (Field.QUANTITY, "worked out as total ÷ price"),
    Amount.PRICE: (Field.PRICE, "worked out as total ÷ quantity"),
    Amount.TOTAL: (Field.TOTAL_VALUE, "worked out as quantity × price"),
}

_GUESSED = {Inferred.QUOTE: Field.QUOTE_ASSET_ID, Inferred.FEE_COIN: Field.FEE_ASSET_ID}


def marks_for(
    record: TradeRecord, check: PriceCheck | None = None, *, asset_name: str | None = None
) -> TradeMarks:
    """Every mark of the trade ``record``; ``check`` is its price against the market price.

    ``asset_name`` is the ledger's name of the asset, said in the reason
    when the model matched it. Example: 0.01 BTC at 950 USDT, the total
    worked out, BTC at 64880 USDT: the total worked out, the price
    suspicious.
    """
    found: list[FieldMark] = []
    if record.derived is not None:
        field, reason = _WORKED_OUT[record.derived]
        found.append(FieldMark(field, MarkKind.COMPUTED, reason))
    source = record.inferred_from
    for guess in sorted(record.inferred, key=lambda one: one.name):
        if source is not None:
            found.append(FieldMark(_GUESSED[guess], MarkKind.INFERRED, _guess_reason(source)))
    if record.picked is not None:
        found.append(
            FieldMark(Field.ASSET_ID, MarkKind.INFERRED, _picked_reason(record, asset_name))
        )
    if check is not None and check.verdict is PriceVerdict.FAR:
        found.append(FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, far_reason(record.coin, check)))
    return TradeMarks(marks=_one_a_cell(found))


def _guess_reason(source: InferredFrom) -> str:
    day = source.occurred.date().isoformat()
    return cut_reason(
        f"assumed from the last {source.asset} trade in the ledger "
        f"({source.trade_id}, {day}), which used {source.money}"
    )


def _picked_reason(record: TradeRecord, name: str | None) -> str:
    named = f"{record.coin} ({name})" if name and name != record.coin else record.coin
    return cut_reason(
        f'"{record.picked}" was matched to {named} from the ledger\'s list of assets by the model'
    )


def far_reason(asset: str, check: PriceCheck) -> str:
    """Why a price far from the market price is suspicious, with every figure it rests on.

    Example: "far from the market price of BTC in the ledger, 64880 USDT on
    2026-11-24 (about 68 times lower)".
    """
    market = check.market
    if check.verdict is not PriceVerdict.FAR or market is None or check.times is None:
        raise ValueError("only a price far from the market price has this reason")
    day = f" on {market.day.isoformat()}" if market.day is not None else ""
    way = "higher" if check.higher else "lower"
    figure = _plain(market.price.amount)
    return cut_reason(
        f"{FAR_REASON_START} of {asset} in the ledger, {figure} {market.price.currency}{day} "
        f"(about {_plain(check.times)} times {way})"
    )


def _plain(value: Decimal) -> str:
    """A figure written out in full, without an exponent. Example: 6.488E+4 -> 64880."""
    return format(value.normalize(), "f") if value == value.to_integral() else format(value, "f")


def _one_a_cell(found: Iterable[FieldMark]) -> tuple[FieldMark, ...]:
    """One mark a cell: the strongest kept, the reason of any dropped put first in its own."""
    by_field: dict[Field, FieldMark] = {}
    for mark in found:
        held = by_field.get(mark.field)
        by_field[mark.field] = mark if held is None else _stronger(held, mark)
    return tuple(by_field[field] for field in Field if field in by_field)


def _stronger(one: FieldMark, other: FieldMark) -> FieldMark:
    """The mark kept of two on one cell, with the other's reason first in its own.

    The dropped reason is cut first, then the kept one, so the two fit.
    Example: a price worked out and far: suspicious, "worked out as total ÷
    quantity; far from the market price ...".
    """
    if _KEPT_FIRST.index(other.kind) < _KEPT_FIRST.index(one.kind):
        one, other = other, one
    if other.reason is None:
        return one
    own = cut_reason(one.reason) if one.reason is not None else ""
    room = REASON_MOST - reason_length(own) - (reason_length(_JOIN) if own else 0)
    if room < reason_length(_ELLIPSIS) + 1:
        return one
    dropped = cut_reason(other.reason, room)
    return FieldMark(one.field, one.kind, f"{dropped}{_JOIN}{own}" if own else dropped)


def fields_sent(facts: TradeFacts) -> frozenset[Field]:
    """The cells of ``facts`` that are sent with a value: a day alone sends no time of day,
    and an empty platform or note, or no rate, is sent as none."""
    given = set(Field) - {Field.PLATFORM, Field.NOTE, Field.COST_RATE}
    if facts.date_only:
        given -= _TIME_OF_DAY
    if facts.platform:
        given.add(Field.PLATFORM)
    if facts.note:
        given.add(Field.NOTE)
    if facts.cost_rate is not None:
        given.add(Field.COST_RATE)
    return frozenset(given)


def as_sent(marks: TradeMarks, sent: frozenset[Field]) -> tuple[dict[str, str | None], ...]:
    """The marks as the ledger takes them, for a trade whose cells ``sent`` hold a value.

    A cell not in ``sent`` (sent empty, or not at all) keeps only a
    suspicious mark; the time of day and the time zone keep none when they
    are not sent. Each mark is the three keys ``field``, ``kind``, ``reason``.
    """
    kept: list[dict[str, str | None]] = []
    for mark in marks.marks:
        if mark.field not in sent and (
            mark.kind is not MarkKind.SUSPICIOUS or mark.field in _TIME_OF_DAY
        ):
            continue
        kept.append({"field": mark.field.value, "kind": mark.kind.value, "reason": mark.reason})
    return tuple(kept)
