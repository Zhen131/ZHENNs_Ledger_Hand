"""What goes on a card: a trade sent with the cells not said, or wrong, left empty and marked.

Since the ledger takes a trade with cells left empty, the assistant no
longer asks one cell at a time (the product owner's rule, 81A section 2
item 1, 2026-11-24): every cell it has is sent; one not said is left
empty for the person to fill in on the ledger's page; one said but wrong
in itself is left empty too, and marked suspicious with what was said and
why it is wrong. Only which asset and buy or sell are still asked, since
the ledger never takes them empty (``flows/recording.py`` decides what is
asked).

``card_record`` takes a draft the check found problems in, and the asset
table and the current moment, and gives a ``CardRecord``: like a
``TradeRecord``, but with the seven cells the ledger lets be empty
perhaps ``None``, and with the doubts the check found (``doubts``),
each a suspicious mark with the user's own value in its reason. It
never fills an empty cell with 0, empty text or a guess.

Cell by cell:

- quantity, price, total: each said and sound is kept; one said but not
  above zero, or with more digits than the ledger holds, is left empty
  and doubted; with two said and sound, the third is worked out as for a
  record; with three that do not agree, the total is left empty and all
  three are doubted with the three figures (the ledger takes no card with
  every cell given whose figures do not agree, 72B, 2026-11-25), and the
  program does not guess which is wrong;
- the money used: as the check reads it, or empty when not settled; a
  vague word the ledger's last trade could not settle is doubted by the
  caller (``money_doubts``);
- the fee: empty when not said; empty and doubted when below zero or too
  long; a fee of 0 is taken in the money used, and is empty with it;
  a fee in the asset bought that is not below the quantity: the quantity
  is kept, the fee left empty, both doubted;
- the time: empty when not said; empty and doubted when after today;
  the day alone, doubted, when its offset has seconds in it;
- the platform, the note: not sent and doubted when longer than the
  ledger allows, with how they began.

``card_marks`` gives every mark of a card: those of a record
(``marks.marks_from``), its doubts, and "25U" taken as the total
(``taken_as_total``), assumed.

Every reason of a doubt starts as one of ``Doubt`` says, so that what is
marked suspicious can be found from here alone.

Names defined here: ``Doubt``, ``CardRecord``, ``card_record``,
``card_marks``, ``money_doubt_two``, ``money_doubt_other`` and
``TAKEN_AS_TOTAL``.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from ledger_hand.core.arithmetic import working_context
from ledger_hand.core.assets import AssetTable
from ledger_hand.core.ledger_limits import (
    NOTE_MAX_LENGTH,
    PLATFORM_MAX_LENGTH,
    fits_digit_limits,
    text_length,
    trim,
)
from ledger_hand.core.marks import Field, FieldMark, MarkKind, TradeMarks, cut_reason, marks_from
from ledger_hand.core.price_check import PriceCheck
from ledger_hand.core.trade import (
    Amount,
    Inferred,
    InferredFrom,
    OccurredTime,
    Side,
    TimePrecision,
    TradeDraft,
)
from ledger_hand.core.validation import (
    DEFAULT_FUTURE_GRACE,
    DraftProblems,
    Missing,
    Violation,
    amounts_agree,
    coin_of,
    fee_coin_of,
    quote_of,
    third_amount,
)

# The reason "25U" taken as the total is assumed with.
TAKEN_AS_TOTAL = '"{said}" was taken as the total spent; quantity and price were not said'

# How many characters of an over-long platform or note the reason shows.
_START_SHOWN = 20

_ONE_MINUTE = timedelta(minutes=1)


class Doubt(enum.Enum):
    """Why a cell of a card is suspicious; the value is the reason, to be filled in.

    Each says what the user said and why it is wrong; the program never
    says which value is right.
    """

    NOT_ABOVE_ZERO = "you said the {cell} was {value}, which is not above zero"
    TOO_MANY_DIGITS = "you said the {cell} was {value}, which has more digits than the ledger holds"
    WORKED_OUT_UNFIT = (
        "the {cell} worked out from the other two came to {value}, which the ledger cannot hold"
    )
    DISAGREE = (
        "you said the total was {total}, but quantity × price is {product}; "
        "the program does not guess which is wrong"
    )
    FEE_BELOW_ZERO = "you said the fee was {value}, which is below zero"
    FEE_NOT_BELOW = (
        "you said the fee was {fee} and the quantity {quantity}, but a fee taken in the asset "
        "bought must be below the quantity; the program does not guess which is wrong"
    )
    FEE_WORD_NOT_A_CODE = 'you said the fee was paid in "{word}", which cannot be an asset code'
    FEE_WORD_UNKNOWN = 'you said the fee was paid in "{word}", which the ledger does not know'
    AFTER_TODAY = "you said {day}, which is after today"
    OFFSET_SECONDS = (
        "the time's offset from UTC has seconds in it, which the ledger cannot write; "
        "only the day {day} is sent"
    )
    TOO_LONG = 'the {cell} is longer than the ledger allows, so it is not sent; it began "{start}"'
    MONEY_TWO_USED = (
        '"{word}" may mean USDT or the US dollar, and the {asset} trades in the ledger on '
        "the latest day it was traded used both"
    )
    MONEY_OTHER_USED = (
        '"{word}" may mean USDT or the US dollar, but the last {asset} trade in the ledger '
        "({trade}, {day}) used {money}"
    )

    @property
    def start(self) -> str:
        """The fixed start of the reason, before anything is filled in."""
        return self.value.split("{", 1)[0]

    @classmethod
    def of(cls, reason: str) -> Doubt | None:
        """Which doubt ``reason`` was made from, or ``None`` for a reason of no doubt.

        A reason cut short still matches by what is left of it. Example:
        "you said the price was 0, which is not above zero" is
        ``NOT_ABOVE_ZERO``.
        """
        text = reason.removesuffix("…")
        for doubt in cls:
            if _pattern(doubt).match(text) or _pattern(doubt, cut=True).match(text):
                return doubt
        return None


def _pattern(doubt: Doubt, *, cut: bool = False) -> re.Pattern[str]:
    """``doubt``'s reason as a pattern: each part filled in matches any text."""
    parts = re.split(r"\{[a-z]+\}", doubt.value)
    body = "(.+?)".join(re.escape(part) for part in parts)
    return re.compile(f"^{body}" if cut else f"^{body}$", re.DOTALL)


def _doubt(field: Field, doubt: Doubt, **filled: object) -> FieldMark:
    return FieldMark(field, MarkKind.SUSPICIOUS, cut_reason(doubt.value.format(**filled)))


def money_doubt_two(word: str, asset: str) -> str:
    """Why a vague word for money is doubted when the asset's latest day used two moneys."""
    return cut_reason(Doubt.MONEY_TWO_USED.value.format(word=word, asset=asset))


def money_doubt_other(word: str, source: InferredFrom) -> str:
    """Why a vague word for money is doubted when the asset's last trade used another money.

    Example: "刀" with ETH last traded in CNY.
    """
    return cut_reason(
        Doubt.MONEY_OTHER_USED.value.format(
            word=word,
            asset=source.asset,
            trade=source.trade_id,
            day=source.occurred.date().isoformat(),
            money=source.money,
        )
    )


_AMOUNT_FIELD = {
    Amount.QUANTITY: Field.QUANTITY,
    Amount.PRICE: Field.PRICE,
    Amount.TOTAL: Field.TOTAL_VALUE,
}


@dataclass(frozen=True, kw_only=True)
class CardRecord:
    """A trade to send as a card: each cell kept, or ``None`` when left empty; and its doubts.

    ``coin`` is a ledger symbol, ``quote`` and ``fee_coin`` codes, as in a
    record. ``occurred`` is ``None`` when the day is left empty; it holds
    the day alone when only the day is sent. ``derived`` names the amount
    the program worked out. ``doubts`` are the suspicious marks the check
    found, one a cell at most. ``taken_as_total`` is the user's words a
    total was read from ("25U"), when a quantity said in money was taken
    as the total. ``inferred``, ``inferred_from`` and ``picked`` are the
    draft's, as for a record.
    """

    side: Side
    coin: str
    quantity: Decimal | None
    price: Decimal | None
    total: Decimal | None
    quote: str | None
    derived: Amount | None
    fee: Decimal | None
    fee_coin: str | None
    occurred: OccurredTime | None
    raw_text: str
    platform: str | None = None
    note: str | None = None
    inferred: frozenset[Inferred] = frozenset()
    inferred_from: InferredFrom | None = None
    picked: str | None = None
    doubts: tuple[FieldMark, ...] = ()
    taken_as_total: str | None = None

    @property
    def empty(self) -> frozenset[Field]:
        """The cells of the seven the ledger lets be empty that are left empty."""
        cells = {
            Field.OCCURRED_DATE: self.occurred,
            Field.QUANTITY: self.quantity,
            Field.PRICE: self.price,
            Field.TOTAL_VALUE: self.total,
            Field.QUOTE_ASSET_ID: self.quote,
            Field.FEE: self.fee,
            Field.FEE_ASSET_ID: self.fee_coin,
        }
        return frozenset(field for field, value in cells.items() if value is None)


def card_record(
    draft: TradeDraft,
    problems: DraftProblems,
    assets: AssetTable,
    now: datetime,
    *,
    money_doubts: Mapping[Field, str] | None = None,
    taken_as_total: str | None = None,
    after_today: str | None = None,
) -> CardRecord:
    """The card of ``draft``: each cell kept, left empty, or left empty and doubted.

    ``problems`` are what the check found in the draft; ``assets`` the
    asset table; ``now`` the current moment, with an offset.
    ``money_doubts`` holds the reason a vague word for the money used, or
    for the fee's money, is doubted, by its cell. ``after_today`` is the
    day (or the words) of a time said that reading refused for lying
    after today ("2026-11-25"), so that the empty day says why. Raises ``ValueError``
    when the side or the asset is not settled: those are asked, never left
    empty.
    """
    if now.utcoffset() is None:
        raise ValueError("the current moment must carry a time zone offset")
    side = draft.side
    coin = coin_of(draft.coin, assets)
    if side is None or coin is None:
        raise ValueError("a card is made only once the side and the asset are settled")
    if draft.raw_text is None:
        raise ValueError("a card keeps what the user said")
    doubts: dict[Field, FieldMark] = {}
    amounts = _amounts(draft, doubts)
    quote = quote_of(draft.quote, assets)
    said_money = dict(money_doubts or {})
    if quote is None and Field.QUOTE_ASSET_ID in said_money:
        _add(
            doubts,
            FieldMark(Field.QUOTE_ASSET_ID, MarkKind.SUSPICIOUS, said_money[Field.QUOTE_ASSET_ID]),
        )
    quantity, price, total, derived = amounts
    fee, fee_coin = _fee(draft, problems, assets, quote, said_money, doubts)
    if (
        side is Side.BUY
        and fee is not None
        and fee_coin == coin
        and quantity is not None
        and fee >= quantity
    ):
        figures = {"fee": _plain(fee) + f" {coin}", "quantity": _plain(quantity) + f" {coin}"}
        _add(doubts, _doubt(Field.QUANTITY, Doubt.FEE_NOT_BELOW, **figures))
        _add(doubts, _doubt(Field.FEE, Doubt.FEE_NOT_BELOW, **figures))
        fee = None
    occurred = _occurred(draft.occurred, now, doubts)
    if occurred is None and draft.occurred is None and after_today is not None:
        _add(doubts, _doubt(Field.OCCURRED_DATE, Doubt.AFTER_TODAY, day=after_today))
    platform = _free_text(draft.platform, "platform", PLATFORM_MAX_LENGTH, Field.PLATFORM, doubts)
    note = _free_text(draft.note, "note", NOTE_MAX_LENGTH, Field.NOTE, doubts, trimmed=False)
    return CardRecord(
        side=side,
        coin=coin,
        quantity=quantity,
        price=price,
        total=total,
        quote=quote,
        derived=derived,
        fee=fee,
        fee_coin=fee_coin,
        occurred=occurred,
        raw_text=draft.raw_text,
        platform=platform,
        note=note,
        inferred=draft.inferred,
        inferred_from=draft.inferred_from,
        picked=draft.picked,
        doubts=tuple(doubts[field] for field in Field if field in doubts),
        taken_as_total=taken_as_total,
    )


def _add(doubts: dict[Field, FieldMark], mark: FieldMark) -> None:
    """Keep ``mark``; a second doubt of the same cell joins the first, the first said first."""
    held = doubts.get(mark.field)
    if held is None or held.reason is None or mark.reason is None:
        doubts[mark.field] = mark
        return
    joined = cut_reason(f"{held.reason}; {mark.reason}")
    doubts[mark.field] = FieldMark(mark.field, MarkKind.SUSPICIOUS, joined)


def _plain(value: Decimal) -> str:
    return format(value, "f")


def _amounts(
    draft: TradeDraft, doubts: dict[Field, FieldMark]
) -> tuple[Decimal | None, Decimal | None, Decimal | None, Amount | None]:
    """Quantity, price and total as sent, and the one worked out; doubts noted in ``doubts``."""
    stated = {amount: value for amount in Amount if (value := draft.stated(amount)) is not None}
    sound: dict[Amount, Decimal] = {}
    for amount, value in stated.items():
        field = _AMOUNT_FIELD[amount]
        if value <= 0:
            _add(
                doubts, _doubt(field, Doubt.NOT_ABOVE_ZERO, cell=amount.value, value=_plain(value))
            )
        elif not fits_digit_limits(value):
            _add(
                doubts, _doubt(field, Doubt.TOO_MANY_DIGITS, cell=amount.value, value=_plain(value))
            )
        else:
            sound[amount] = value
    derived: Amount | None = None
    if len(stated) == 2 and len(sound) == 2:
        (blank,) = set(Amount) - set(sound)
        worked = third_amount(blank, sound)
        if worked is None:
            product = _product(blank, sound)
            _add(
                doubts,
                _doubt(
                    _AMOUNT_FIELD[blank], Doubt.WORKED_OUT_UNFIT, cell=blank.value, value=product
                ),
            )
        else:
            sound[blank] = worked
            derived = blank
    if len(stated) == 3 and len(sound) == 3:
        quantity, price, total = sound[Amount.QUANTITY], sound[Amount.PRICE], sound[Amount.TOTAL]
        if not amounts_agree(quantity, price, total):
            figures = {
                "total": _plain(total) + _money_of(draft),
                "product": _plain(working_context().multiply(quantity, price)) + _money_of(draft),
            }
            for field in (Field.QUANTITY, Field.PRICE, Field.TOTAL_VALUE):
                _add(doubts, _doubt(field, Doubt.DISAGREE, **figures))
            del sound[Amount.TOTAL]
    return (
        sound.get(Amount.QUANTITY),
        sound.get(Amount.PRICE),
        sound.get(Amount.TOTAL),
        derived,
    )


def _money_of(draft: TradeDraft) -> str:
    """The user's word for the money, after a figure, when one was said."""
    return f" {draft.quote}" if draft.quote else ""


def _product(blank: Amount, sound: Mapping[Amount, Decimal]) -> str:
    """The third amount as it came out unrounded, for the reason it was not kept."""
    context = working_context()
    if blank is Amount.TOTAL:
        return _plain(context.multiply(sound[Amount.QUANTITY], sound[Amount.PRICE]))
    other = Amount.PRICE if blank is Amount.QUANTITY else Amount.QUANTITY
    return _plain(context.divide(sound[Amount.TOTAL], sound[other]))


def _fee(
    draft: TradeDraft,
    problems: DraftProblems,
    assets: AssetTable,
    quote: str | None,
    said_money: Mapping[Field, str],
    doubts: dict[Field, FieldMark],
) -> tuple[Decimal | None, str | None]:
    """The fee and what it was taken in, as sent; doubts noted in ``doubts``."""
    fee = draft.fee
    if fee is None:
        return None, None
    if fee < 0:
        _add(doubts, _doubt(Field.FEE, Doubt.FEE_BELOW_ZERO, value=_plain(fee)))
        return None, None
    if not fits_digit_limits(fee):
        _add(doubts, _doubt(Field.FEE, Doubt.TOO_MANY_DIGITS, cell="fee", value=_plain(fee)))
        return None, None
    if fee.is_zero():
        return fee.copy_abs(), quote
    coin = fee_coin_of(draft, assets)
    if coin is not None:
        return fee, coin
    word = draft.fee_coin or ""
    if Violation.FEE_COIN_NOT_A_SYMBOL in problems.violations:
        _add(doubts, _doubt(Field.FEE_ASSET_ID, Doubt.FEE_WORD_NOT_A_CODE, word=word))
    elif Missing.FEE_COIN_CONFIRMATION in problems.missing:
        _add(doubts, _doubt(Field.FEE_ASSET_ID, Doubt.FEE_WORD_UNKNOWN, word=word))
    elif Field.FEE_ASSET_ID in said_money:
        reason = said_money[Field.FEE_ASSET_ID]
        _add(doubts, FieldMark(Field.FEE_ASSET_ID, MarkKind.SUSPICIOUS, reason))
    return fee, None


def _occurred(
    occurred: OccurredTime | None, now: datetime, doubts: dict[Field, FieldMark]
) -> OccurredTime | None:
    """The time as sent: none, the time as said, or the day alone; doubts noted."""
    if occurred is None:
        return None
    if occurred.is_in_the_future(now, DEFAULT_FUTURE_GRACE):
        said = occurred.calendar_date.isoformat()
        _add(doubts, _doubt(Field.OCCURRED_DATE, Doubt.AFTER_TODAY, day=said))
        return None
    value = occurred.value
    if isinstance(value, datetime):
        offset = value.utcoffset()
        if offset is not None and offset % _ONE_MINUTE:
            day = occurred.calendar_date
            _add(doubts, _doubt(Field.OCCURRED_DATE, Doubt.OFFSET_SECONDS, day=day.isoformat()))
            return OccurredTime(day, TimePrecision.DAY, occurred.time_zone)
    return occurred


def _free_text(
    text: str | None,
    cell: str,
    most: int,
    field: Field,
    doubts: dict[Field, FieldMark],
    *,
    trimmed: bool = True,
) -> str | None:
    """A platform or a note as sent: ``None`` when not given, or too long (then doubted)."""
    if text is None:
        return None
    kept = trim(text) if trimmed else text
    if text_length(kept) > most:
        start = kept.strip()[:_START_SHOWN]
        _add(doubts, _doubt(field, Doubt.TOO_LONG, cell=cell, start=start))
        return None
    return kept or None


def card_marks(
    card: CardRecord, check: PriceCheck | None, *, asset_name: str | None = None
) -> TradeMarks:
    """Every mark of ``card``: a record's, its doubts, and a total taken from "25U".

    Example: 0.094326 SOL at 212.03 USDT, 200 USDT said in all: the
    quantity, the price and the total are suspicious, the total empty.
    """
    assumed: tuple[FieldMark, ...] = ()
    if card.taken_as_total is not None and card.total is not None:
        reason = cut_reason(TAKEN_AS_TOTAL.format(said=card.taken_as_total))
        assumed = (FieldMark(Field.TOTAL_VALUE, MarkKind.INFERRED, reason),)
    return marks_from(
        coin=card.coin,
        derived=card.derived,
        inferred=card.inferred,
        inferred_from=card.inferred_from,
        picked=card.picked,
        check=check,
        asset_name=asset_name,
        doubts=card.doubts,
        assumed=assumed,
        empty=card.empty,
    )
