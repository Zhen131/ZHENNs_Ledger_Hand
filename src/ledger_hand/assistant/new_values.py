"""The new value of a change, read from the user's words, and the trade it makes.

The model copies the new value from what the user said; the program reads
it, by the field it is for, and never guesses. Two steps:

``read_new_value`` reads the words alone, before any trade is found:

- quantity, price, total, fee: one number, read by ``core.numbers``; a
  number read with a caution ("1.500" may be one thousand five hundred)
  is not taken. It must be above zero; a fee may be zero. A unit beside it
  is kept, and checked once the trade is known.
- time: read by ``core.timeparse``. Only a moment is taken: a day with no
  time of day, a time with a caution ("3点" with no half of the day), a
  time the clocks showed twice, one in the future and words that cannot be
  read are not; no clock time is made up and no earlier one kept.
- side: one of the fixed words for a buy or a sell.
- asset, the money it is priced in, the asset the fee is taken in: one
  asset of the ledger, by its code, name or another name the coin table
  gives it; the money it is priced in must be one that can price a trade.
- platform, note: the words as they are, within the ledger's length.

``changed_trade`` then puts the value into the trade found:

- a unit with a number must name what that field holds now: the trade's
  asset for the quantity (a counter such as "个" is taken there too), the
  money it is priced in for the price and the total, the asset the fee is
  taken in for the fee. Any other unit, or one not known, changes nothing:
  the program changes one thing at a time. Whether "U" or "美元" name USDT
  is not settled, so only the ledger's own code, name and the coin table's
  other names count;
- a value the trade already has changes nothing;
- a new quantity, price or total that leaves quantity times price away
  from the total, beyond the ledger's tolerance, is not put in alone: the
  program works out, by the ledger's own rules (``core.validation``), what
  each of the other two would become, and the user says which follows
  (``Fixes``). One that cannot be worked out to fit the ledger is not
  offered; with none left, nothing changes.

Every figure in the trade that comes out is the ledger's, the user's, or
worked out by the program; none is the model's. The words the trade was
recorded from are kept as they were.

Names defined here: ``NumberValue``, ``TimeValue``, ``SideValue``,
``AssetValue``, ``TextValue``, ``NewValue``, ``NotTaken``, ``Fix``,
``Fixes``, ``Unchanged``, ``read_new_value``, ``changed_trade`` and
``with_fix``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ledger_hand.assistant.narrowing import assets_named
from ledger_hand.core.ledger_limits import (
    NOTE_MAX_LENGTH,
    PLATFORM_MAX_LENGTH,
    fits_digit_limits,
    text_length,
)
from ledger_hand.core.ledger_records import Asset, Pricing, TradeFacts
from ledger_hand.core.numbers import NotANumber, Recognised, Unsure, read_number
from ledger_hand.core.timeparse import TimeRecognised, TimeRefused, TwoCandidates, read_time
from ledger_hand.core.trade import Amount, Side, TimePrecision
from ledger_hand.core.validation import amounts_agree, third_amount
from ledger_hand.extraction.answer_words import SIDE_WORDS, tidy

_NUMBER_FIELDS = {
    "quantity": Amount.QUANTITY,
    "price": Amount.PRICE,
    "total": Amount.TOTAL,
    "fee": None,
}
_ASSET_FIELDS = frozenset({"asset", "quote_currency", "fee_currency"})
_TEXT_FIELDS = {"platform": PLATFORM_MAX_LENGTH, "note": NOTE_MAX_LENGTH}
_COUNTERS = ("个", "個", "枚", "颗", "顆")
# Which of the other two amounts is offered first to follow a changed one.
_FOLLOWERS = {
    Amount.QUANTITY: (Amount.TOTAL, Amount.PRICE),
    Amount.PRICE: (Amount.TOTAL, Amount.QUANTITY),
    Amount.TOTAL: (Amount.PRICE, Amount.QUANTITY),
}
# The words the program uses for each field when it speaks.
FIELD_WORDS = {
    "quantity": "quantity",
    "price": "price",
    "total": "total",
    "fee": "fee",
    "time": "time",
    "side": "side",
    "asset": "asset",
    "quote_currency": "money it is priced in",
    "fee_currency": "asset the fee is taken in",
    "platform": "platform",
    "note": "note",
}


@dataclass(frozen=True)
class NumberValue:
    """A number read, and the unit written with it, as written, if there was one."""

    value: Decimal
    unit: str | None = None


@dataclass(frozen=True)
class TimeValue:
    """A moment read, with its offset."""

    moment: datetime


@dataclass(frozen=True)
class SideValue:
    side: Side


@dataclass(frozen=True)
class AssetValue:
    """The code of one asset of the ledger."""

    code: str


@dataclass(frozen=True)
class TextValue:
    text: str


type NewValue = NumberValue | TimeValue | SideValue | AssetValue | TextValue


@dataclass(frozen=True)
class NotTaken:
    """The new value is not taken, and why, in the program's words for the user."""

    words: str


@dataclass(frozen=True)
class Fix:
    """One way to put the three amounts back in step: which follows, and all three after."""

    follows: Amount
    quantity: Decimal
    price: Decimal
    total: Decimal


@dataclass(frozen=True)
class Fixes:
    """The new amount leaves the three out of step: the ways to put them back, to choose from."""

    changed: Amount
    fixes: tuple[Fix, ...]


@dataclass(frozen=True)
class Unchanged:
    """The trade already has this value: there is nothing to change."""


def _not_read(words: str, field: str, why: str) -> NotTaken:
    return NotTaken(
        f"I could not take {words!r} as the new {FIELD_WORDS[field]}: {why}. "
        "Nothing was changed; please say it another way."
    )


def read_new_value(
    field: str, words: str, assets: Sequence[Asset], *, now: datetime, zone: str
) -> NewValue | NotTaken:
    """The new value for ``field``, read from the user's ``words``, or why it is not taken."""
    if field in _NUMBER_FIELDS:
        return _number(field, words, assets)
    if field == "time":
        return _time(words, now, zone)
    if field == "side":
        side = SIDE_WORDS.get(tidy(words))
        return SideValue(side) if side is not None else _not_read(words, field, "not buy or sell")
    if field in _ASSET_FIELDS:
        return _asset(field, words, assets)
    if field in _TEXT_FIELDS:
        if text_length(words) > _TEXT_FIELDS[field]:
            return _not_read(words, field, "it is longer than the ledger allows")
        return TextValue(words)
    raise ValueError(f"no such field: {field!r}")


def _number(field: str, words: str, assets: Sequence[Asset]) -> NumberValue | NotTaken:
    names = [name for asset in assets for name in (asset.code, asset.name)]
    reading = read_number(words, extra_units=names)
    if isinstance(reading, NotANumber):
        return _not_read(words, field, "it is not a number")
    if isinstance(reading, Unsure):
        return _not_read(words, field, reading.reason.value)
    assert isinstance(reading, Recognised)
    if reading.cautions:
        return _not_read(words, field, reading.cautions[0].value)
    value = reading.value
    if value < 0 or (value == 0 and field != "fee"):
        return _not_read(words, field, "it must be above zero")
    if not fits_digit_limits(value):
        return _not_read(words, field, "it has more digits than the ledger holds")
    return NumberValue(value=value, unit=reading.unit)


def _time(words: str, now: datetime, zone: str) -> TimeValue | NotTaken:
    reading = read_time(words, now, zone)
    if isinstance(reading, TimeRefused):
        return _not_read(words, "time", reading.reason.value)
    if isinstance(reading, TwoCandidates):
        return _not_read(words, "time", "the clocks showed that time twice that day")
    assert isinstance(reading, TimeRecognised)
    if reading.cautions:
        return _not_read(words, "time", reading.cautions[0].value)
    if reading.time.precision is TimePrecision.DAY:
        return NotTaken(
            f"{words!r} gives the day but not the time of day. Nothing was changed; "
            "please say the day and the time together, such as '10月6号11:48'."
        )
    moment = reading.time.value
    assert isinstance(moment, datetime)
    return TimeValue(moment)


def _asset(field: str, words: str, assets: Sequence[Asset]) -> AssetValue | NotTaken:
    codes = assets_named(words, assets)
    if len(codes) != 1:
        return NotTaken(
            f"The ledger has no asset called {words!r}, so nothing was changed."
            if not codes
            else f"{words!r} names more than one asset, so nothing was changed."
        )
    (code,) = codes
    pricing = next(asset.pricing for asset in assets if asset.code == code)
    if field == "quote_currency" and pricing is not Pricing.CAN_PRICE:
        return NotTaken(f"{code} cannot be the money a trade is priced in, so nothing was changed.")
    return AssetValue(code)


def _holds(field: str, trade: TradeFacts) -> str:
    """The asset whose amount ``field`` is, in ``trade``."""
    if field == "quantity":
        return trade.asset
    return trade.fee_asset if field == "fee" else trade.quote


def _unit_names(unit: str, field: str, code: str, assets: Sequence[Asset]) -> bool:
    """Whether ``unit`` names what ``field`` holds now, the asset ``code``."""
    rest = unit.strip()
    if field == "quantity":
        for counter in _COUNTERS:
            rest = rest.removeprefix(counter).strip()
        if not rest:
            return True
    return assets_named(rest, assets) == frozenset({code})


def changed_trade(
    field: str, value: NewValue, trade: TradeFacts, assets: Sequence[Asset]
) -> TradeFacts | Fixes | Unchanged | NotTaken:
    """``trade`` with ``field`` set to ``value``, or the choice to make, or why not."""
    if isinstance(value, NumberValue):
        return _with_number(field, value, trade, assets)
    if isinstance(value, TimeValue):
        changed = dataclasses.replace(trade, occurred=value.moment)
    elif isinstance(value, SideValue):
        changed = dataclasses.replace(trade, side=value.side)
    elif isinstance(value, AssetValue):
        changed = _with_asset(field, value.code, trade)
    elif field == "platform":
        changed = dataclasses.replace(trade, platform=value.text)
    else:
        changed = dataclasses.replace(trade, note=value.text)
    return Unchanged() if changed == trade else changed


def _with_asset(field: str, code: str, trade: TradeFacts) -> TradeFacts:
    if field == "asset":
        return dataclasses.replace(trade, asset=code)
    if field == "quote_currency":
        return dataclasses.replace(trade, quote=code)
    return dataclasses.replace(trade, fee_asset=code)


def _with_number(
    field: str, value: NumberValue, trade: TradeFacts, assets: Sequence[Asset]
) -> TradeFacts | Fixes | Unchanged | NotTaken:
    code = _holds(field, trade)
    if value.unit is not None and not _unit_names(value.unit, field, code, assets):
        return NotTaken(
            f"'{value.unit}' is not {code}, what the {FIELD_WORDS[field]} is in now. That would "
            "change two things, the number and what it is in, and I change one at a time, so "
            "nothing was changed. To change what the fee is taken in, say that alone."
        )
    amount = _NUMBER_FIELDS[field]
    if amount is None:
        return (
            Unchanged() if value.value == trade.fee else dataclasses.replace(trade, fee=value.value)
        )
    now = {Amount.QUANTITY: trade.quantity, Amount.PRICE: trade.price, Amount.TOTAL: trade.total}
    if value.value == now[amount]:
        return Unchanged()
    after = {**now, amount: value.value}
    if amounts_agree(after[Amount.QUANTITY], after[Amount.PRICE], after[Amount.TOTAL]):
        return _with_amounts(trade, after)
    fixes = []
    for follows in _FOLLOWERS[amount]:
        kept = ({amount} | set(Amount)) - {follows}
        worked_out = third_amount(follows, {part: after[part] for part in kept})
        if worked_out is not None:
            fixed = {**after, follows: worked_out}
            fixes.append(
                Fix(
                    follows=follows,
                    quantity=fixed[Amount.QUANTITY],
                    price=fixed[Amount.PRICE],
                    total=fixed[Amount.TOTAL],
                )
            )
    if not fixes:
        return NotTaken(
            f"With the new {FIELD_WORDS[field]}, quantity times price no longer matches the "
            "total, and neither of the other two can be worked out to fit the ledger, so "
            "nothing was changed."
        )
    return Fixes(changed=amount, fixes=tuple(fixes))


def _with_amounts(trade: TradeFacts, amounts: dict[Amount, Decimal]) -> TradeFacts:
    return dataclasses.replace(
        trade,
        quantity=amounts[Amount.QUANTITY],
        price=amounts[Amount.PRICE],
        total=amounts[Amount.TOTAL],
    )


def with_fix(trade: TradeFacts, fix: Fix) -> TradeFacts:
    """``trade`` with the three amounts of ``fix``."""
    return dataclasses.replace(trade, quantity=fix.quantity, price=fix.price, total=fix.total)
