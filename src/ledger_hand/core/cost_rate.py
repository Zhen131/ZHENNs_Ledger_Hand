"""The rate between the money paid and the asset's own money, for a trade paid in another money.

A trade may be paid in one money for an asset the ledger prices in another:
two shares of KO, priced in US dollars, bought for 128 euros. The ledger
then wants its rate (``costRate``): how many units of the asset's own money
one unit of the money paid is worth (the ledger's ``assistant-link/README.md``,
"Paying in a currency other than the asset's own needs costRate"). The
assistant cannot read the ledger's rates, so the rate is worked out from
the price of one share the user said in the asset's own money:

    rate = quantity × price said ÷ total paid

rounded half up to ``RATE_PLACES`` (10) places, the zeros at its end left
out, so that the ledger takes it as it is written (at most 18 places).
Example: 2 shares at 69.5 USD for 128 EUR give 2 × 69.5 ÷ 128 = 1.0859375
(USD for 1 EUR). The total paid is taken without any FX fee, which is the
fee (decided on 2026-11-25, 88 items 28 and 29).

Two guards against a figure said wrong:

- the rate against the ledger's own exchange rate between the two moneys,
  when the ledger has one up to the trade's day (``core/ledger_rate.py``,
  2026-11-27), unless that one is dated before the latest trade below;
  otherwise against the rate of the latest trade in the ledger paid in the
  same money for an asset priced in the same money (``reference_in``): far
  when ``|rate ÷ reference − 1|`` is above a share the settings hold, ten
  in a hundred by default; exactly that share is not far
  (``far_from_reference``). With neither, nothing is compared;
- the price said against the ledger's market price of the asset, both in
  the asset's own money, by the market price check (``price_check``).

Either one far makes the rate's mark suspicious; otherwise it is assumed
when the money of the price said was guessed ("美金"), and worked out when
it was named (``rate_mark``). The reason keeps every part, as every mark
does: the ones of a kind pushed out first, then the suspicious ones, cut to
the ledger's 256 UTF-16 units, the first part first.

Nothing here reads the ledger or the clock.

Names defined here: ``RATE_PLACES``, ``rate_of``, ``written``,
``RateReference``, ``reference_in``, ``far_from_reference``, ``RateNote``,
``rate_mark``, ``ledger_far_reason``, ``price_in_paid_reason`` and
``with_rate_marks``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ledger_hand.core.arithmetic import round_half_up, working_context
from ledger_hand.core.ledger_rate import LedgerRateNote, LedgerRateOutcome
from ledger_hand.core.ledger_records import LedgerTrade
from ledger_hand.core.marks import (
    REASON_MOST,
    Field,
    FieldMark,
    MarkKind,
    TradeMarks,
    cut_reason,
    far_reason,
    own_money_reason,
    reason_length,
)
from ledger_hand.core.price_check import PriceCheck, PriceVerdict
from ledger_hand.core.trade import SaidPrice

# How many places after the point a rate is worked out to. Ten keep the rate
# exact enough that the cost the ledger works out with it is off by less than
# a millionth of a dollar on a trade of a few thousand; the ledger takes up to
# 18. Chosen by the contract's author on 2026-11-25, with no source behind it.
RATE_PLACES = 10

_JOIN = "; "
_AS_OF_TODAY = "no day was said, so it was compared as of today"
_ELLIPSIS = "…"


def rate_of(quantity: Decimal, said: Decimal, total: Decimal) -> Decimal:
    """``quantity × said ÷ total``, half up to ``RATE_PLACES`` places, its ending zeros left out.

    Every figure must be above 0. Example: 2, 69.5 and 128 give 1.0859375;
    3, 36.2 and 100 give 1.086.
    """
    if quantity <= 0 or said <= 0 or total <= 0:
        raise ValueError("a rate is worked out from figures above 0")
    context = working_context()
    exact = context.divide(context.multiply(quantity, said), total)
    rounded = round_half_up(exact, RATE_PLACES)
    if rounded <= 0:
        raise ValueError(f"the rate of {quantity} × {said} ÷ {total} rounds to 0")
    return _without_ending_zeros(rounded)


def written(value: Decimal) -> str:
    """``value`` written out in full, with no exponent and no zeros at its end. 1.0860 -> 1.086."""
    return format(_without_ending_zeros(value), "f")


def _without_ending_zeros(value: Decimal) -> Decimal:
    normal = value.normalize(context=working_context())
    if normal == normal.to_integral_value():
        return normal.quantize(Decimal(1))
    return normal


@dataclass(frozen=True, kw_only=True)
class RateReference:
    """The trade a rate is compared with: its rate, identifier, day and asset.

    Example: 1.0859 from trade "t-ko-eur" of AAPL on 2026-11-03.
    """

    rate: Decimal
    trade_id: str
    day: date
    asset: str


def reference_in(
    trades: Sequence[LedgerTrade],
    paid: str,
    own_money: str,
    priced_in: Mapping[str, str],
    now: datetime,
) -> RateReference | None:
    """The latest trade of ``trades`` up to ``now`` paid in ``paid``, with a rate, for an asset
    ``priced_in`` says is priced in ``own_money``; ``None`` when there is none.

    Example: AAPL bought for EUR at a rate of 1.0859 on 2026-11-03 is the
    reference for KO bought for EUR, both shares priced in USD.
    """
    found = [
        trade
        for trade in trades
        if trade.facts.quote == paid
        and trade.facts.cost_rate is not None
        and priced_in.get(trade.facts.asset) == own_money
        and trade.facts.occurred <= now
    ]
    if not found:
        return None
    latest = max(found, key=lambda trade: trade.facts.occurred)
    rate = latest.facts.cost_rate
    assert rate is not None
    return RateReference(
        rate=rate, trade_id=latest.id, day=latest.facts.day, asset=latest.facts.asset
    )


def far_from_reference(rate: Decimal, reference: Decimal, share: Decimal) -> bool:
    """Whether ``rate`` is further from ``reference`` than ``share`` of it, either way.

    Exactly that share is not far. Example: 10.859375 against 1.0859 with
    0.1: far; 1.0859375 against 1.0859: not.
    """
    if reference <= 0:
        raise ValueError("a rate is compared with a reference above 0")
    context = working_context()
    return abs(context.subtract(context.divide(rate, reference), 1)) > share


@dataclass(frozen=True, kw_only=True)
class RateNote:
    """What became of one trade paid in another money, for the words said and the record.

    ``rate`` is the rate sent; ``said`` the price said in the asset's own
    money; ``quantity`` and ``total`` the figures it was worked out from;
    ``each`` the word for one unit ("a share", "a coin"). ``reference`` is
    the trade compared with, or ``None`` when there was none, and
    ``reference_far`` whether the rate is far from it. ``market`` is the
    price said against the market price, or ``None`` when not compared.
    ``dropped_disagrees`` says a price said in the money paid was not used
    and does not agree with the total over the quantity. ``ledger`` is
    what came of the ledger's own exchange rate (``LedgerRateNote``), or
    ``None`` where the ledger was not asked; when it was compared with,
    ``reference`` is ``None`` and ``reference_far`` false.
    """

    rate: Decimal
    said: SaidPrice
    quantity: Decimal
    total: Decimal
    each: str
    reference: RateReference | None = None
    reference_far: bool = False
    market: PriceCheck | None = None
    dropped_disagrees: bool = False
    ledger: LedgerRateNote | None = None

    @property
    def market_far(self) -> bool:
        """Whether the price said is far from the ledger's market price."""
        return self.market is not None and self.market.verdict is PriceVerdict.FAR


def rate_mark(note: RateNote, asset: str) -> FieldMark:
    """The one mark on the rate of a trade paid in another money, with every reason it rests on.

    Suspicious when the rate is far from its reference or the price said
    far from the market price; otherwise assumed when the money of the
    price said was guessed, worked out when it was named. Example:
    "worked out from the 69.5 USD a share you said: 2 × 69.5 ÷ 128".
    """
    said = note.said
    plain: list[str] = []
    source = said.guessed_from
    if source is not None and source.own_money is not None:
        plain.append(f"the money of the price said was {own_money_reason(source)}")
    elif source is not None:
        plain.append(
            f"the money of the price said was assumed from the last {source.asset} trade in the "
            f"ledger ({source.trade_id}, {source.occurred.date().isoformat()}), "
            f"which used {source.money}"
        )
    plain.append(
        f"worked out from the {written(said.amount)} {said.money} {note.each} you said: "
        f"{written(note.quantity)} × {written(said.amount)} ÷ {written(note.total)}"
    )
    doubts: list[str] = []
    ledger = note.ledger
    if ledger is not None and ledger.outcome is LedgerRateOutcome.COMPARED and ledger.far:
        doubts.append(ledger_far_reason(ledger, said.paid, said.money))
    elif ledger is not None and ledger.picked is not None and not ledger.day_said:
        plain.append(_AS_OF_TODAY)
    reference = note.reference
    if note.reference_far and reference is not None:
        doubts.append(
            f"{written(note.rate)} is far from {written(reference.rate)} of the {said.paid} "
            f"trade on {reference.day.isoformat()}"
        )
    market = note.market
    if market is not None and market.verdict is PriceVerdict.FAR:
        doubts.append(
            f"the {written(said.amount)} {said.money} {note.each} you said is "
            f"{far_reason(asset, market)}"
        )
    if not doubts:
        kind = MarkKind.INFERRED if source is not None else MarkKind.COMPUTED
        return FieldMark(Field.COST_RATE, kind, cut_reason(_JOIN.join(plain)))
    # As for every mark: the reason of the kind pushed out goes first, and is
    # cut first, so that the suspicious reasons are kept whole where they fit.
    kept = cut_reason(_JOIN.join(doubts))
    room = REASON_MOST - reason_length(kept) - reason_length(_JOIN)
    if room <= reason_length(_ELLIPSIS):
        return FieldMark(Field.COST_RATE, MarkKind.SUSPICIOUS, kept)
    dropped = cut_reason(_JOIN.join(plain), room)
    return FieldMark(Field.COST_RATE, MarkKind.SUSPICIOUS, f"{dropped}{_JOIN}{kept}")


def ledger_far_reason(ledger: LedgerRateNote, paid: str, own_money: str) -> str:
    """The reason on a rate far from the ledger's own exchange rate: that rate as ``own_money``
    for 1 ``paid`` and its day first, then where it came from, then how long before the trade.

    Example: "far from the ledger's rate 1.3 USD for 1 EUR on 2026-11-20 (typed in by hand)".
    """
    picked = ledger.picked
    assert picked is not None
    reason = (
        f"far from the ledger's rate {written(picked.converted)} {own_money} for 1 {paid} "
        f"on {picked.day.isoformat()} ({picked.row.where_from}"
    )
    if ledger.long_ago:
        reason += f", {ledger.days_apart} days before the trade"
    reason += ")"
    if not ledger.day_said:
        reason += f"; {_AS_OF_TODAY}"
    return reason


def price_in_paid_reason(paid: str) -> str:
    """The reason on a price worked out as the total over the quantity, in the money paid."""
    return f"worked out as total ÷ quantity, in {paid}"


def with_rate_marks(marks: TradeMarks, note: RateNote, asset: str) -> TradeMarks:
    """``marks`` of a trade paid in another money, with its rate's mark and its price's money.

    The price worked out says it is in the money paid ("worked out as total
    ÷ quantity, in EUR"); the rate gets its one mark (``rate_mark``).
    Every other mark stays as it is.
    """
    kept: list[FieldMark] = []
    for mark in marks.marks:
        if mark.field is Field.PRICE and mark.kind is MarkKind.COMPUTED:
            mark = FieldMark(Field.PRICE, MarkKind.COMPUTED, price_in_paid_reason(note.said.paid))
        if mark.field is not Field.COST_RATE:
            kept.append(mark)
    kept.append(rate_mark(note, asset))
    ordered = tuple(sorted(kept, key=lambda mark: list(Field).index(mark.field)))
    return TradeMarks(marks=ordered, empty=marks.empty)
