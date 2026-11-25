"""The fake ledger's sums and holdings, worked out from a replay of its trades.

``period_summary`` sums the trades of a stretch of days (each on the day of
its own offset, both ends counted): for each money they were priced in, how
many buys and sells, what the buys spent, what the sells brought in, the
profit or loss of the sells (``moving_average`` works each one out), all
told and for each asset, and the fees, one sum for each asset they were
taken in. Money of two kinds is never added together. Fees taken in the
money are not added into what was spent or brought in: the fake ledger's
sums are its own, not the real ledger's. ``positions`` gives each holding that is
not empty, with its profit or loss on paper at the market price the book
gives, or why it is not worked out (no market price, or a pool whose
figures are broken).

Names defined here: ``period_summary`` and ``positions``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from ledger_hand.core.arithmetic import round_half_up, working_context
from ledger_hand.core.ledger_records import (
    AssetRealized,
    CurrencyTotals,
    Figure,
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    PeriodSummary,
    Position,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.trade import Side
from ledger_hand.ledger.moving_average import PLACES, Pool, Replay


def period_summary(
    trades: Sequence[tuple[str, TradeFacts]], replayed: Replay, request: PeriodRequest
) -> PeriodSummary:
    """The sums of the trades ``request`` names; ``replayed`` holds each sell's profit or loss."""
    context = working_context()
    days = TradeFilter(first_day=request.first_day, last_day=request.last_day, asset=request.asset)
    chosen = [(key, facts) for key, facts in trades if days.holds(facts)]
    groups: dict[str, _Group] = {}
    for key, facts in chosen:
        group = groups.setdefault(facts.quote, _Group())
        if facts.side is Side.BUY:
            group.buys += 1
            group.spent = context.add(group.spent, facts.total)
        else:
            group.sells += 1
            group.received = context.add(group.received, facts.total)
            figure = replayed.realized[key]
            group.realized.append(figure)
            group.by_asset.setdefault(facts.asset, []).append(figure)
        group.fees[facts.fee_asset] = context.add(
            group.fees.get(facts.fee_asset, Decimal(0)), facts.fee
        )
    return PeriodSummary(
        request=request,
        by_currency=tuple(_totals(quote, groups[quote]) for quote in sorted(groups)),
    )


@dataclass
class _Group:
    """What one money's group gathers while the trades are gone through."""

    buys: int = 0
    sells: int = 0
    spent: Decimal = Decimal(0)
    received: Decimal = Decimal(0)
    realized: list[Figure] = field(default_factory=list)
    by_asset: dict[str, list[Figure]] = field(default_factory=dict)
    fees: dict[str, Decimal] = field(default_factory=dict)


def _totals(quote: str, group: _Group) -> CurrencyTotals:
    realized = _added(quote, group.realized)
    rows = []
    for asset in sorted(group.by_asset):
        figure = _added(quote, group.by_asset[asset])
        if isinstance(figure, MoneyAmount):
            rows.append(AssetRealized(asset=asset, realized=figure, unreliable=None))
    return CurrencyTotals(
        currency=quote,
        buy_count=group.buys,
        sell_count=group.sells,
        spent=MoneyAmount(currency=quote, amount=group.spent),
        received=MoneyAmount(currency=quote, amount=group.received),
        fees=tuple(
            MoneyAmount(currency=asset, amount=group.fees[asset]) for asset in sorted(group.fees)
        ),
        realized=realized,
        realized_from_sells=realized,
        # The fake ledger moves nothing out, so no cost leaves with a transfer.
        realized_from_transfers=MoneyAmount(currency=quote, amount=Decimal(0)),
        by_asset=tuple(rows),
    )


def _added(quote: str, figures: list[Figure]) -> Figure:
    """The figures added together, or the first reason one of them was not worked out."""
    context = working_context()
    total = Decimal(0)
    for figure in figures:
        if isinstance(figure, NotWorkedOut):
            return figure
        total = context.add(total, figure.amount)
    return MoneyAmount(currency=quote, amount=total)


def positions(replayed: Replay, prices: Mapping[tuple[str, str], Decimal]) -> tuple[Position, ...]:
    """Every holding that is not empty, in the order of asset and money."""
    return tuple(
        _position(pool, prices.get((pool.asset, pool.quote)))
        for _, pool in sorted(replayed.pools.items())
        if pool.quantity > 0
    )


def _position(pool: Pool, price: Decimal | None) -> Position:
    context = working_context()
    unrealized: Figure
    if pool.broken is not None:
        unrealized = NotWorkedOut(reason=pool.broken)
    elif price is None:
        unrealized = NotWorkedOut(
            reason=f"there is no market price for {pool.asset} in {pool.quote}"
        )
    else:
        worth = context.multiply(pool.quantity, price)
        amount = round_half_up(context.subtract(worth, pool.cost), PLACES)
        unrealized = MoneyAmount(currency=pool.quote, amount=amount)
    return Position(
        asset=pool.asset,
        currency=pool.quote,
        quantity=pool.quantity,
        cost=MoneyAmount(currency=pool.quote, amount=pool.cost),
        cost_unreliable=None,
        unrealized=unrealized,
    )
