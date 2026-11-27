"""The ledger's exchange rates, asked for once for each pair of moneys of one proposal.

A trade paid in one money P for an asset the ledger prices in another money
Q has its rate compared, before it is sent, with the ledger's own exchange
rate between P and Q (``core/ledger_rate.py``). This program asks for it
itself, never the model (the ledger's tool ``list_exchange_rates``).

``looked_up`` asks the ledger once for each pair of moneys of the proposal:
both moneys by the ledger's identifiers, taken from the list of assets this
proposal already holds; up to the latest day of the trades of that pair;
pages read until the earliest. A money the list does not hold, one two
assets share, or one that is not cash is never asked about: nothing is
said of the ledger then, but that it has no rate between the two moneys
(a ledger asked would only answer ``ASSET_NOT_FOUND`` or
``ASSET_IS_NOT_CURRENCY``, every time). A ledger that cannot be asked
never stops the trade: it is sent all the same, and its rate compared
with the last trade paid the same way, as before. Which failure is said
in this program's own words and which in the ledger's goes by its code
alone (``QUOTED_CODES``).

``ledger_note`` says, for one trade, what came of it (``LedgerRateNote``):

- the row picked (``core/ledger_rate.pick``) is compared with, unless it
  is dated before the last trade in the ledger paid the same way, which is
  then compared with instead (the nearer one is used; one as near, the
  ledger's rate);
- no row fits: the last trade is compared with, as before;
- the ledger has no tool for it (an older one): the last trade is
  compared with, as before, and nothing more is said.

The day a trade is compared on is its own day, in its own zone; a trade
that said no day is compared on today, in the user's zone, and says so.

Names defined here: ``QUOTED_CODES``, ``Looked``, ``trade_day``,
``looked_up`` and ``ledger_note``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ledger_hand.core.cost_rate import RateReference
from ledger_hand.core.ledger_rate import (
    NO_RATE_TOOL,
    LedgerRateNote,
    LedgerRateOutcome,
    RateList,
    RateRequest,
    pick,
    rate_gap,
)
from ledger_hand.core.ledger_records import Asset, AssetKind
from ledger_hand.core.zones import zone_named
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort

# The ledger's codes whose own words are said when it turns the question down;
# every other failure is said in this program's words (decided on 2026-11-27).
QUOTED_CODES = frozenset(
    {
        "INVALID_ARGUMENTS",
        "INVALID_DATE",
        "START_DATE_AFTER_END_DATE",
        "ASSET_NOT_FOUND",
        "ASSET_IS_NOT_CURRENCY",
        "UNEXPECTED_PROGRAM_ERROR",
    }
)
_LATE = "the ledger took too long to answer"
_CHANGING = "the ledger kept changing while they were read"
_CHANGED = "LEDGER_CHANGED_START_FROM_FIRST_PAGE"


@dataclass(frozen=True, kw_only=True)
class Looked:
    """What came of asking the ledger for the rates between one pair of moneys.

    ``rows`` and the identifiers when it answered; otherwise ``outcome``
    says how it ended, with the ledger's code and words, or this program's.
    """

    outcome: LedgerRateOutcome | None = None
    rates: RateList | None = None
    paid_id: str | None = None
    own_id: str | None = None
    code: str | None = None
    message: str | None = None
    why: str | None = None


def trade_day(occurred_day: date | None, now: datetime, zone: str) -> tuple[date, bool]:
    """The day a trade's rate is compared on, and whether the trade said it.

    ``occurred_day`` is the trade's own day in its own zone, or ``None``
    when it said none: then today in ``zone``. Example: no day said, now
    2026-11-24 10:00 in Budapest: 24 November 2026, not said.
    """
    if occurred_day is not None:
        return occurred_day, True
    return now.astimezone(zone_named(zone)).date(), False


def looked_up(
    ledger: LedgerPort,
    assets: Mapping[str, Asset],
    pairs: Mapping[tuple[str, str], Sequence[date]],
) -> dict[tuple[str, str], Looked]:
    """For each pair (money paid, asset's own money) and the days of its trades: the rates."""
    found: dict[tuple[str, str], Looked] = {}
    for (paid, own), days in pairs.items():
        paid_asset, own_asset = assets.get(paid), assets.get(own)
        if not _cash(paid_asset) or not _cash(own_asset):
            found[(paid, own)] = Looked(outcome=LedgerRateOutcome.NONE_FITTING)
            continue
        assert paid_asset is not None and own_asset is not None
        request = RateRequest(
            currency_id=paid_asset.id,
            other_id=own_asset.id,
            last_day=max(days),
            enough_day=min(days),
        )
        try:
            listed = ledger.exchange_rates(request)
        except LedgerError as error:
            found[(paid, own)] = _failed(error)
            continue
        found[(paid, own)] = Looked(rates=listed, paid_id=paid_asset.id, own_id=own_asset.id)
    return found


def _cash(asset: Asset | None) -> bool:
    return asset is not None and asset.kind is AssetKind.CASH


def _failed(error: LedgerError) -> Looked:
    if error.code == NO_RATE_TOOL:
        return Looked(outcome=LedgerRateOutcome.NO_TOOL, code=error.code)
    if error.code in QUOTED_CODES:
        return Looked(outcome=LedgerRateOutcome.REFUSED, code=error.code, message=error.message)
    if error.kind is LedgerErrorKind.TIMED_OUT:
        why: str | None = _LATE
    elif error.code == _CHANGED:
        why = _CHANGING
    else:
        why = None
    return Looked(outcome=LedgerRateOutcome.NOT_READ, code=error.code, why=why)


def ledger_note(
    rate: Decimal,
    looked: Looked,
    day: date,
    *,
    day_said: bool,
    reference: RateReference | None,
    limit: Decimal,
) -> LedgerRateNote:
    """What came of the ledger's rate for one trade whose rate is ``rate``, on ``day``.

    ``reference`` is the last trade paid the same way, or ``None``;
    ``limit`` how far apart, in a hundred, is far.
    """
    if looked.outcome is not None:
        return LedgerRateNote(
            outcome=looked.outcome,
            day=day,
            day_said=day_said,
            code=looked.code,
            message=looked.message,
            why=looked.why,
            limit=limit,
        )
    assert looked.rates is not None and looked.paid_id is not None and looked.own_id is not None
    picked, passed_over = pick(looked.rates.rows, looked.paid_id, looked.own_id, day)
    if picked is None:
        return LedgerRateNote(
            outcome=LedgerRateOutcome.NONE_FITTING,
            day=day,
            day_said=day_said,
            passed_over=passed_over,
            limit=limit,
        )
    gap = rate_gap(rate, picked)
    older = reference is not None and picked.day < reference.day
    return LedgerRateNote(
        outcome=LedgerRateOutcome.OLDER_THAN_TRADE if older else LedgerRateOutcome.COMPARED,
        day=day,
        day_said=day_said,
        picked=picked,
        gap=gap,
        far=not older and gap > limit / 100,
        limit=limit,
        days_apart=(day - picked.day).days,
        passed_over=passed_over,
    )
