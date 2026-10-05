"""Pairing the drafts of one passage with its gold trades, whatever order the drafts came in.

When a passage holds several trades, each draft has to be set against the
gold trade it stands for before any field can be scored. The rule:

1. As many pairs are made as there can be: the smaller of the number of
   gold trades and the number of drafts. The gold trades left over are
   missed; the drafts left over are extra.
2. Among all such pairings, the one with the most fields in agreement, added
   up over its pairs, is taken. A field agrees when the draft holds the gold
   value, both put in the same form (``cells.agrees``), and both empty
   agrees too.
3. Where several pairings agree on as many fields, the drafts are first put
   in a fixed order of their own content, and the first such pairing in that
   order is taken. Two drafts that come first in that order equally hold the
   same values in every scored field, so which of them goes in a pair changes
   no score. So the order the model gave its rows in changes nothing.

The pairing is found exactly, by trying every assignment over the gold
trades, which a passage has only a few of.

Names defined here: ``pair_trades``, ``Pairing`` and ``MAX_GOLD_TRADES``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from evals.cells import SCORED_FIELDS, agrees, draft_value, shown
from evals.gold import GoldTrade
from ledger_hand.core.trade import TradeDraft

# Far more trades than a test sentence holds; it keeps the exact search small
# (it grows with two to the power of this).
MAX_GOLD_TRADES = 12


@dataclass(frozen=True)
class Pairing:
    """Which draft goes with which gold trade, and what is left over.

    ``pairs`` holds (gold position, draft position) in the order of the gold
    trades; ``missed`` the positions of gold trades with no draft; ``extra``
    the positions of drafts with no gold trade.
    """

    pairs: tuple[tuple[int, int], ...]
    missed: tuple[int, ...]
    extra: tuple[int, ...]


def agreement(gold: GoldTrade, draft: TradeDraft) -> int:
    """How many scored fields of ``draft`` hold the gold value."""
    return sum(
        agrees(field, gold.value(field), draft_value(draft, field)) for field in SCORED_FIELDS
    )


def _content_key(draft: TradeDraft) -> str:
    """The draft's scored values as one text, to put drafts in an order of their own content."""
    return json.dumps([shown(draft_value(draft, field)) for field in SCORED_FIELDS])


def pair_trades(gold: Sequence[GoldTrade], drafts: Sequence[TradeDraft]) -> Pairing:
    """The pairing of ``drafts`` with ``gold``, by the rule above."""
    if len(gold) > MAX_GOLD_TRADES:
        raise ValueError(f"at most {MAX_GOLD_TRADES} gold trades can be paired")
    order = sorted(range(len(drafts)), key=lambda position: _content_key(drafts[position]))
    weights = [[agreement(trade, drafts[position]) for trade in gold] for position in order]
    chosen = _best_assignment(weights, len(gold))
    pairs = sorted((gold_at, order[rank]) for rank, gold_at in chosen.items())
    taken_gold = {gold_at for gold_at, _ in pairs}
    taken_drafts = {draft_at for _, draft_at in pairs}
    return Pairing(
        pairs=tuple(pairs),
        missed=tuple(at for at in range(len(gold)) if at not in taken_gold),
        extra=tuple(at for at in range(len(drafts)) if at not in taken_drafts),
    )


def _best_assignment(weights: list[list[int]], gold_count: int) -> dict[int, int]:
    """For drafts in order, the gold trade each is paired with: most pairs, then most weight.

    ``weights[rank][g]`` is how many fields the draft at ``rank`` agrees on
    with gold trade ``g``. Dynamic programming over the drafts in order and
    the set of gold trades already taken; on a tie the earlier choice stays.
    """
    # best[mask] = (pairs, weight, choices) for the drafts seen so far.
    best: dict[int, tuple[int, int, tuple[tuple[int, int], ...]]] = {0: (0, 0, ())}
    for rank, row in enumerate(weights):
        following = dict(best)
        for mask, (count, weight, choices) in best.items():
            for gold_at in range(gold_count):
                if mask & (1 << gold_at):
                    continue
                candidate = (count + 1, weight + row[gold_at], (*choices, (rank, gold_at)))
                key = mask | (1 << gold_at)
                current = following.get(key)
                if current is None or candidate[:2] > current[:2]:
                    following[key] = candidate
        best = following
    top = max(best.values(), key=lambda entry: entry[:2])
    return dict(top[2])
