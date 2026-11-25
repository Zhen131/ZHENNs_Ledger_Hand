"""The check: a draft goes in; a finished record, or two lists of problems, comes out.

``check_draft`` takes a draft, the asset table, the current moment and a few
adjustable settings. A draft that is complete and sound becomes a
``TradeRecord``. Any other draft comes back as ``DraftProblems``: what is
still missing, and what breaks a rule. A draft that falls short is an ordinary
result, not an error, so nothing is raised for it; and every problem is
reported at once, not just the first one found. Each list is in the order its
enumeration is written below, whatever order the problems were found in.

The rules:

- The side, the coin, the time, the fee and the original text must be there.
- The coin must be an asset of the asset table or confirmed by the user
  (when the table lets an unseen asset be confirmed), must be writable as a
  ledger symbol, and cannot be a money the table prices trades in.
- The trade is priced in one money the table prices trades in. When no word
  for it was said, or the word names more than one such money, a table
  with only one takes that one, and a table with several asks which. A word
  for any other money, or for no money, means the trade cannot be recorded.
- Of quantity, price and total, at least two must be stated. The third is
  calculated and marked as calculated. If all three are stated, quantity times
  price may differ from the total by no more than the tolerance, and all three
  are kept as stated.
- Every amount must be above zero, and a stated number must fit the ledger's
  digit limits as it stands: it is never rounded silently.
- A calculated quotient that comes out even, and that the ledger can hold in
  full, is kept whole. Otherwise it is rounded half up to ``derived_places``.
  A calculated total is rounded half up to the most decimal places the ledger
  holds. After rounding, the calculated amount must itself be above zero and
  fit the ledger, and the three amounts must still agree.
- The fee must be stated, even when it is zero, and cannot be negative. A fee
  above zero needs its coin: a money the table prices trades in, or an asset
  the table knows. A word naming more than one such money counts as no
  word. A fee of zero is always recorded in the money the trade is priced
  in.
- On a buy, a fee paid in the coin being bought must be smaller than the
  quantity.
- The time cannot be in the future: a moment may be at most ``future_grace``
  after the current moment, and a day may not be after today in the trade's
  own time zone.
- A moment's offset from UTC must be a whole number of minutes. Some zones
  had offsets with seconds in them before the 1970s, such as ``+01:16:20`` in
  Budapest in 1890, and the ledger's way of writing a time cannot hold one.
  A time known only to the day carries no offset and is not affected.
- The original text cannot be empty; it, the note and the platform have the
  ledger's length limits. The platform is recorded without surrounding
  whitespace, and a platform of whitespace alone counts as not given.

Holdings are not checked: this program does not know what the ledger already
holds, so a sale is never refused for selling more than was bought.

All arithmetic goes through the contexts of ``arithmetic``, never through
Python's default one. The agreement of the three amounts is also tested the
way the ledger itself calculates it, so that a record accepted here is not
turned down there over its total.

``third_amount`` and ``amounts_agree`` give the same working out to a
change of a trade already in the ledger: when one of the three amounts is
changed, the program asks which of the other two follows, and works that
one out here, by the very rules a draft's third amount is worked out by.

Names defined here: ``check_draft``, ``Missing``, ``Violation``,
``DraftProblems``, ``CheckSettings``, ``DEFAULT_SETTINGS``,
``DEFAULT_DERIVED_PLACES``, ``DEFAULT_FUTURE_GRACE``, ``third_amount`` and
``amounts_agree``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Context, Decimal, Inexact

from ledger_hand.core.arithmetic import ledger_context, round_half_up, working_context
from ledger_hand.core.assets import AssetTable, MoneyReading, UnknownAssets
from ledger_hand.core.coins import spoken_key
from ledger_hand.core.ledger_limits import (
    MAX_DECIMAL_PLACES,
    NOTE_MAX_LENGTH,
    PLATFORM_MAX_LENGTH,
    RAW_TEXT_MAX_LENGTH,
    TOTAL_TOLERANCE,
    fits_digit_limits,
    is_symbol,
    text_length,
    trim,
)
from ledger_hand.core.trade import Amount, OccurredTime, Side, TradeDraft, TradeRecord


class Missing(enum.Enum):
    """Something the user still has to supply before the draft can become a record."""

    SIDE = "whether it was a buy or a sell"
    COIN = "the coin"
    COIN_CONFIRMATION = "confirmation of a coin not seen before"
    TWO_OF_QUANTITY_PRICE_TOTAL = "two of quantity, price and total"
    ONE_MORE_OF_QUANTITY_PRICE_TOTAL = "one more of quantity, price and total"
    FEE = "the fee, even if it was zero"
    FEE_COIN = "the coin the fee was paid in"
    FEE_COIN_CONFIRMATION = "confirmation of a fee coin not seen before"
    OCCURRED = "when the trade happened"
    RAW_TEXT = "the original text"
    QUOTE = "the currency the trade was priced in"


class Violation(enum.Enum):
    """Something in the draft that breaks a rule and has to be corrected."""

    COIN_IS_USDT = "the traded coin is USDT, the pricing currency itself"
    COIN_NOT_A_SYMBOL = "the coin is unknown and cannot be written as a ledger symbol"
    UNSUPPORTED_QUOTE = "the trade is priced in something other than USDT"
    QUANTITY_NOT_POSITIVE = "the quantity is not above zero"
    PRICE_NOT_POSITIVE = "the price is not above zero"
    TOTAL_NOT_POSITIVE = "the total is not above zero"
    QUANTITY_TOO_MANY_DIGITS = "the quantity has more digits than the ledger holds"
    PRICE_TOO_MANY_DIGITS = "the price has more digits than the ledger holds"
    TOTAL_TOO_MANY_DIGITS = "the total has more digits than the ledger holds"
    AMOUNTS_DISAGREE = "quantity times price does not match the total"
    FEE_NEGATIVE = "the fee is below zero"
    FEE_TOO_MANY_DIGITS = "the fee has more digits than the ledger holds"
    FEE_COIN_NOT_A_SYMBOL = "the fee coin is unknown and cannot be written as a ledger symbol"
    FEE_NOT_BELOW_QUANTITY = "a buy fee paid in the bought coin is not below the quantity"
    IN_THE_FUTURE = "the trade is dated in the future"
    OFFSET_HAS_SECONDS = (
        "the time's offset from UTC has seconds in it, which the ledger cannot write"
    )
    PLATFORM_TOO_LONG = "the platform is longer than the ledger allows"
    NOTE_TOO_LONG = "the note is longer than the ledger allows"
    RAW_TEXT_EMPTY = "the original text is empty"
    RAW_TEXT_TOO_LONG = "the original text is longer than the ledger allows"
    COIN_IS_PRICING_MONEY = "the traded asset is a currency trades are priced in"
    QUOTE_CANNOT_PRICE = "the trade is priced in a currency the ledger does not price trades in"
    ASSET_NOT_IN_LEDGER = "the asset is not in the ledger; add it there first"
    FEE_ASSET_NOT_IN_LEDGER = "the fee's asset is not in the ledger; add it there first"


@dataclass(frozen=True)
class DraftProblems:
    """Why a draft is not a record yet; each list is in the order of its enumeration."""

    missing: tuple[Missing, ...]
    violations: tuple[Violation, ...]


DEFAULT_DERIVED_PLACES = 8
DEFAULT_FUTURE_GRACE = timedelta(minutes=1)


@dataclass(frozen=True, kw_only=True)
class CheckSettings:
    """The adjustable parts of the check.

    ``derived_places``: decimal places kept when a calculated quantity or
    price does not come out even. More than the ledger holds would produce
    numbers the ledger refuses.

    ``total_tolerance``: how far quantity times price may be from the total.
    It may be tightened; a looser value than the ledger's would let through
    trades the ledger turns down.

    ``future_grace``: how far after the current moment a trade's moment may
    lie, to allow for clocks that are slightly apart.
    """

    derived_places: int = DEFAULT_DERIVED_PLACES
    total_tolerance: Decimal = TOTAL_TOLERANCE
    future_grace: timedelta = DEFAULT_FUTURE_GRACE

    def __post_init__(self) -> None:
        if not 0 <= self.derived_places <= MAX_DECIMAL_PLACES:
            raise ValueError(f"derived_places must be from 0 to {MAX_DECIMAL_PLACES}")
        tolerance = self.total_tolerance
        if not tolerance.is_finite() or not 0 <= tolerance <= TOTAL_TOLERANCE:
            raise ValueError(f"total_tolerance must be from 0 to {TOTAL_TOLERANCE}")
        if self.future_grace < timedelta(0):
            raise ValueError("future_grace cannot be negative")


DEFAULT_SETTINGS = CheckSettings()

_ONE_MINUTE = timedelta(minutes=1)

_Problem = Missing | Violation

_NOT_POSITIVE = {
    Amount.QUANTITY: Violation.QUANTITY_NOT_POSITIVE,
    Amount.PRICE: Violation.PRICE_NOT_POSITIVE,
    Amount.TOTAL: Violation.TOTAL_NOT_POSITIVE,
}
_TOO_MANY_DIGITS = {
    Amount.QUANTITY: Violation.QUANTITY_TOO_MANY_DIGITS,
    Amount.PRICE: Violation.PRICE_TOO_MANY_DIGITS,
    Amount.TOTAL: Violation.TOTAL_TOO_MANY_DIGITS,
}


@dataclass(frozen=True)
class _Amounts:
    quantity: Decimal
    price: Decimal
    total: Decimal
    derived: Amount | None


@dataclass(frozen=True)
class _Fee:
    amount: Decimal
    coin: str | None


def check_draft(
    draft: TradeDraft,
    assets: AssetTable,
    now: datetime,
    settings: CheckSettings = DEFAULT_SETTINGS,
) -> TradeRecord | DraftProblems:
    """Turn ``draft`` into a record, or say what is missing and what breaks a rule.

    ``assets`` says which assets may be traded and which money they may be
    priced in. ``now`` is the current moment and must carry an offset; the
    check never reads a clock itself.
    """
    if now.utcoffset() is None:
        raise ValueError("the current moment must carry a time zone offset")
    found: list[_Problem] = []
    side = draft.side
    if side is None:
        found.append(Missing.SIDE)
    coin = _coin_symbol(draft.coin, assets, found)
    quote = _quote(draft.quote, assets, found)
    amounts = _amounts(draft, settings, found)
    fee = _fee(draft, assets, quote, found)
    _check_fee_below_quantity(side, coin, amounts, fee, found)
    occurred = _occurred(draft.occurred, now, settings.future_grace, found)
    platform = _platform(draft.platform, found)
    note = _note(draft.note, found)
    raw_text = _raw_text(draft.raw_text, found)
    if (
        found
        or side is None
        or coin is None
        or quote is None
        or amounts is None
        or fee is None
        or fee.coin is None
        or occurred is None
        or raw_text is None
    ):
        return _in_fixed_order(found)
    return TradeRecord(
        side=side,
        coin=coin,
        quantity=amounts.quantity,
        price=amounts.price,
        total=amounts.total,
        quote=quote,
        derived=amounts.derived,
        fee=fee.amount,
        fee_coin=fee.coin,
        occurred=occurred,
        raw_text=raw_text,
        platform=platform,
        note=note,
    )


def _in_fixed_order(found: list[_Problem]) -> DraftProblems:
    return DraftProblems(
        missing=tuple(item for item in Missing if item in found),
        violations=tuple(item for item in Violation if item in found),
    )


# --- the coin and the pricing currency --------------------------------------


def _coin_symbol(spoken: str | None, assets: AssetTable, found: list[_Problem]) -> str | None:
    if spoken is None or not spoken_key(spoken):
        found.append(Missing.COIN)
        return None
    reading = assets.money(spoken).reading
    if reading in (MoneyReading.ONE, MoneyReading.SEVERAL):
        found.append(
            Violation.COIN_IS_USDT
            if assets.speaks_of_usdt_only()
            else Violation.COIN_IS_PRICING_MONEY
        )
        return None
    if assets.from_ledger and reading is MoneyReading.CANNOT_PRICE:
        # Money of the ledger that prices nothing, traded as an asset: an
        # exchange of money, which the assistant leaves to the ledger.
        found.append(Violation.ASSET_NOT_IN_LEDGER)
        return None
    coin = assets.find(spoken)
    if coin is not None:
        return coin.symbol
    if assets.is_shielded(spoken):
        found.append(Violation.ASSET_NOT_IN_LEDGER)
    elif not is_symbol(spoken_key(spoken)):
        found.append(Violation.COIN_NOT_A_SYMBOL)
    elif assets.unknown is UnknownAssets.CONFIRM_ON_THE_SPOT:
        found.append(Missing.COIN_CONFIRMATION)
    else:
        found.append(Violation.ASSET_NOT_IN_LEDGER)
    return None


def _quote(spoken: str | None, assets: AssetTable, found: list[_Problem]) -> str | None:
    """The code of the money the trade is priced in, or ``None`` with the problem noted."""
    said = assets.money(spoken) if spoken is not None and spoken_key(spoken) else None
    if said is None or said.reading is MoneyReading.SEVERAL:
        # Not said, or not clear which: a table with one money needs no answer.
        sole = assets.sole_pricing_code
        if sole is None:
            found.append(Missing.QUOTE)
        return sole
    if said.reading is MoneyReading.ONE:
        return said.code
    found.append(
        Violation.UNSUPPORTED_QUOTE
        if assets.speaks_of_usdt_only()
        else Violation.QUOTE_CANNOT_PRICE
    )
    return None


# --- quantity, price and total ----------------------------------------------


def _amounts(draft: TradeDraft, settings: CheckSettings, found: list[_Problem]) -> _Amounts | None:
    stated = {amount: value for amount in Amount if (value := draft.stated(amount)) is not None}
    soundness = [_is_sound(amount, value, found) for amount, value in stated.items()]
    if len(stated) < 2:
        found.append(
            Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL
            if stated
            else Missing.TWO_OF_QUANTITY_PRICE_TOTAL
        )
        return None
    if not all(soundness):
        return None
    derived = None
    if len(stated) == 2:
        (derived,) = set(Amount) - set(stated)
        stated[derived] = _derive(derived, stated, settings.derived_places)
        if not _is_sound(derived, stated[derived], found):
            return None
    amounts = _Amounts(stated[Amount.QUANTITY], stated[Amount.PRICE], stated[Amount.TOTAL], derived)
    if not _agree(amounts, settings.total_tolerance):
        found.append(Violation.AMOUNTS_DISAGREE)
        return None
    return amounts


def _is_sound(amount: Amount, value: Decimal, found: list[_Problem]) -> bool:
    """Whether one amount is above zero and fits the ledger's digit limits."""
    positive = value > 0
    fits = fits_digit_limits(value)
    if not positive:
        found.append(_NOT_POSITIVE[amount])
    if not fits:
        found.append(_TOO_MANY_DIGITS[amount])
    return positive and fits


def _derive(blank: Amount, stated: Mapping[Amount, Decimal], places: int) -> Decimal:
    """The one amount that was not stated, calculated from the two that were."""
    if blank is Amount.TOTAL:
        product = working_context().multiply(stated[Amount.QUANTITY], stated[Amount.PRICE])
        return _written_plainly(round_half_up(product, MAX_DECIMAL_PLACES))
    divisor = stated[Amount.PRICE if blank is Amount.QUANTITY else Amount.QUANTITY]
    return _written_plainly(_quotient(stated[Amount.TOTAL], divisor, places))


def _quotient(dividend: Decimal, divisor: Decimal, places: int) -> Decimal:
    """``dividend / divisor``, kept whole or rounded.

    A quotient that comes out even, and that the ledger can hold in full, is
    kept as it is. Any other is rounded half up to ``places``.
    """
    context = working_context()
    quotient = context.divide(dividend, divisor)
    if not context.flags[Inexact] and fits_digit_limits(quotient):
        return quotient
    return round_half_up(quotient, places)


def _written_plainly(value: Decimal) -> Decimal:
    """The same number without trailing zeros after the point.

    Left in, they would count against the ledger's digit limits.
    """
    text = format(value, "f")
    return Decimal(text.rstrip("0").rstrip(".") if "." in text else text)


def _agree(amounts: _Amounts, tolerance: Decimal) -> bool:
    """Whether quantity times price is close enough to the total, here and in the ledger."""
    here = _gap(working_context(), amounts) <= tolerance
    in_the_ledger = _gap(ledger_context(), amounts) <= TOTAL_TOLERANCE
    return here and in_the_ledger


def _gap(context: Context, amounts: _Amounts) -> Decimal:
    product = context.multiply(amounts.quantity, amounts.price)
    return context.subtract(product, amounts.total).copy_abs()


# --- the third amount of a trade already in the ledger -----------------------


def third_amount(blank: Amount, stated: Mapping[Amount, Decimal]) -> Decimal | None:
    """The amount ``blank``, worked out from the other two in ``stated``, as a draft's is.

    The working out is the one ``check_draft`` gives a draft with these two
    stated and the default settings: a total is rounded to the most places
    the ledger holds, a quantity or a price is kept whole when it comes out
    even and fits, and is otherwise rounded half up to
    ``DEFAULT_DERIVED_PLACES``. ``None`` when the result is not above zero,
    does not fit the ledger's digit limits, or, after rounding, the three
    amounts still do not agree. Raises ``ValueError`` when ``stated`` does
    not hold exactly the two other amounts, each above zero.
    """
    others = set(Amount) - {blank}
    if set(stated) != others or not all(stated[amount] > 0 for amount in others):
        raise ValueError("stated holds the two other amounts, each above zero")
    value = _derive(blank, stated, DEFAULT_DERIVED_PLACES)
    if not value > 0 or not fits_digit_limits(value):
        return None
    every = {**stated, blank: value}
    amounts = _Amounts(every[Amount.QUANTITY], every[Amount.PRICE], every[Amount.TOTAL], blank)
    return value if _agree(amounts, TOTAL_TOLERANCE) else None


def amounts_agree(quantity: Decimal, price: Decimal, total: Decimal) -> bool:
    """Whether quantity times price is within the ledger's tolerance of the total.

    It is the test ``check_draft`` puts the three amounts of a draft to,
    with the ledger's own tolerance, here and as the ledger works it out.
    """
    return _agree(_Amounts(quantity, price, total, None), TOTAL_TOLERANCE)


# --- the fee ----------------------------------------------------------------


def _fee(
    draft: TradeDraft, assets: AssetTable, quote: str | None, found: list[_Problem]
) -> _Fee | None:
    fee = draft.fee
    if fee is None:
        found.append(Missing.FEE)
        return None
    negative = fee < 0
    fits = fits_digit_limits(fee)
    if negative:
        found.append(Violation.FEE_NEGATIVE)
    if not fits:
        found.append(Violation.FEE_TOO_MANY_DIGITS)
    if negative or not fits:
        return None
    if fee.is_zero():
        # Recorded in the money the trade is priced in; while that is not
        # settled, a problem is already noted and no record is built.
        return _Fee(fee.copy_abs(), quote)
    coin = _fee_coin_symbol(draft, assets, found)
    return None if coin is None else _Fee(fee, coin)


def _fee_coin_symbol(draft: TradeDraft, assets: AssetTable, found: list[_Problem]) -> str | None:
    spoken = draft.fee_coin
    said = None if spoken is None or not spoken_key(spoken) else assets.money(spoken)
    if spoken is None or said is None or said.reading is MoneyReading.SEVERAL:
        # Not said, or not clear which money: asked as the fee's coin.
        found.append(Missing.FEE_COIN)
        return None
    if said.reading is MoneyReading.ONE:
        return said.code
    if assets.from_ledger and said.reading is MoneyReading.CANNOT_PRICE and said.code is not None:
        # A fee may be taken in money of the ledger that prices no trade.
        return said.code
    coin = assets.find(spoken)
    if coin is not None:
        return coin.symbol
    key = spoken_key(spoken)
    same_as_coin = draft.coin is not None and spoken_key(draft.coin) == key
    if assets.is_shielded(spoken):
        if not same_as_coin:
            found.append(Violation.FEE_ASSET_NOT_IN_LEDGER)
    elif not is_symbol(key):
        found.append(Violation.FEE_COIN_NOT_A_SYMBOL)
    elif not same_as_coin:
        # The same unseen coin as the trade itself is confirmed once, or
        # refused once, as the trade's coin; only a different one is taken
        # up on its own.
        found.append(
            Missing.FEE_COIN_CONFIRMATION
            if assets.unknown is UnknownAssets.CONFIRM_ON_THE_SPOT
            else Violation.FEE_ASSET_NOT_IN_LEDGER
        )
    return None


def _check_fee_below_quantity(
    side: Side | None,
    coin: str | None,
    amounts: _Amounts | None,
    fee: _Fee | None,
    found: list[_Problem],
) -> None:
    if side is not Side.BUY or amounts is None or fee is None:
        return
    if fee.coin == coin and fee.amount >= amounts.quantity:
        found.append(Violation.FEE_NOT_BELOW_QUANTITY)


# --- the time ---------------------------------------------------------------


def _occurred(
    occurred: OccurredTime | None, now: datetime, grace: timedelta, found: list[_Problem]
) -> OccurredTime | None:
    if occurred is None:
        found.append(Missing.OCCURRED)
        return None
    in_the_future = occurred.is_in_the_future(now, grace)
    seconds_in_offset = _offset_has_seconds(occurred)
    if in_the_future:
        found.append(Violation.IN_THE_FUTURE)
    if seconds_in_offset:
        found.append(Violation.OFFSET_HAS_SECONDS)
    return None if in_the_future or seconds_in_offset else occurred


def _offset_has_seconds(occurred: OccurredTime) -> bool:
    """Whether the time is a moment whose offset is not a whole number of minutes."""
    if not isinstance(occurred.value, datetime):
        return False
    offset = occurred.value.utcoffset()
    return offset is not None and bool(offset % _ONE_MINUTE)


# --- free text --------------------------------------------------------------


def _platform(text: str | None, found: list[_Problem]) -> str | None:
    trimmed = "" if text is None else trim(text)
    if text_length(trimmed) > PLATFORM_MAX_LENGTH:
        found.append(Violation.PLATFORM_TOO_LONG)
    return trimmed or None


def _note(text: str | None, found: list[_Problem]) -> str | None:
    if text is not None and text_length(text) > NOTE_MAX_LENGTH:
        found.append(Violation.NOTE_TOO_LONG)
    return text


def _raw_text(text: str | None, found: list[_Problem]) -> str | None:
    if text is None:
        found.append(Missing.RAW_TEXT)
        return None
    if not trim(text).strip():
        found.append(Violation.RAW_TEXT_EMPTY)
        return None
    if text_length(text) > RAW_TEXT_MAX_LENGTH:
        found.append(Violation.RAW_TEXT_TOO_LONG)
        return None
    return text
