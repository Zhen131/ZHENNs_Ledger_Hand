"""The fake ledger's way of working out cost and profit: a moving average.

``replay`` goes through trades oldest first and keeps one pool for each
asset and the money it was bought with: how much is held and what it cost.
A buy adds its quantity and its total to the pool; a sell takes out its
quantity at the pool's average cost, and its profit or loss is what it
brought in less that cost. A fee taken in the asset bought or sold changes
the quantity; one taken in the money of the pool changes the cost or what a
sell brought in. A fee taken in any third asset cannot be put into that
money, so from then on the pool's figures are not worked out, and say why.
A sell of more than the pool holds is not worked out either.

This is the fake ledger's own way, simple enough to check by hand. It does
not stand for how the real ledger works its figures out, and nothing should
be built on the two agreeing.

Figures are rounded half up to ``PLACES`` digits after the point, each time
one is worked out.

Names defined here: ``PLACES``, ``Pool``, ``Replay`` and ``replay``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from ledger_hand.core.arithmetic import round_half_up, working_context
from ledger_hand.core.ledger_records import Figure, MoneyAmount, NotWorkedOut, TradeFacts
from ledger_hand.core.trade import Side

# Eight places: the finest step of a bitcoin, plenty for a fake ledger's figures.
PLACES = 8


@dataclass
class Pool:
    """One asset bought with one money: how much is held, what it cost, and whether
    the figures can still be worked out (``broken`` says why not)."""

    asset: str
    quote: str
    quantity: Decimal = Decimal(0)
    cost: Decimal = Decimal(0)
    broken: str | None = None


@dataclass
class Replay:
    """What a replay found: the pools, and each sell's profit or loss by its trade's key."""

    pools: dict[tuple[str, str], Pool] = field(default_factory=dict)
    realized: dict[str, Figure] = field(default_factory=dict)
    oversold: list[str] = field(default_factory=list)


def replay(trades: Iterable[tuple[str, TradeFacts]]) -> Replay:
    """Go through ``trades`` (each a key and its facts) oldest first, and keep the pools."""
    found = Replay()
    for key, facts in sorted(trades, key=lambda pair: pair[1].occurred):
        pool = found.pools.setdefault(
            (facts.asset, facts.quote), Pool(asset=facts.asset, quote=facts.quote)
        )
        if facts.fee_asset not in (facts.asset, facts.quote) and pool.broken is None:
            pool.broken = (
                f"a fee was taken in {facts.fee_asset}, whose worth in {facts.quote} is not known"
            )
        if facts.side is Side.BUY:
            _buy(pool, facts)
        else:
            found.realized[key] = _sell(pool, facts, key, found.oversold)
    return found


def _buy(pool: Pool, facts: TradeFacts) -> None:
    context = working_context()
    received = facts.quantity
    if facts.fee_asset == facts.asset:
        received = context.subtract(received, facts.fee)
    paid = facts.total
    if facts.fee_asset == facts.quote:
        paid = context.add(paid, facts.fee)
    pool.quantity = context.add(pool.quantity, received)
    pool.cost = round_half_up(context.add(pool.cost, paid), PLACES)


def _sell(pool: Pool, facts: TradeFacts, key: str, oversold: list[str]) -> Figure:
    context = working_context()
    leaving = facts.quantity
    if facts.fee_asset == facts.asset:
        leaving = context.add(leaving, facts.fee)
    if leaving > pool.quantity or pool.quantity == 0:
        oversold.append(key)
        pool.broken = pool.broken or f"more {facts.asset} was sold than was held"
        pool.quantity = max(Decimal(0), context.subtract(pool.quantity, leaving))
        return NotWorkedOut(reason=pool.broken)
    share = context.divide(leaving, pool.quantity)
    cost_out = round_half_up(context.multiply(pool.cost, share), PLACES)
    pool.quantity = context.subtract(pool.quantity, leaving)
    pool.cost = context.subtract(pool.cost, cost_out)
    if pool.broken is not None:
        return NotWorkedOut(reason=pool.broken)
    brought_in = facts.total
    if facts.fee_asset == facts.quote:
        brought_in = context.subtract(brought_in, facts.fee)
    profit = round_half_up(context.subtract(brought_in, cost_out), PLACES)
    return MoneyAmount(currency=facts.quote, amount=profit)
