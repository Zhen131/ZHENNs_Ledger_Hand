"""A trade paid in one money for an asset the ledger prices in another: when, and how it is sent.

"今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元": KO is priced
in US dollars, the trade was paid in euros. The ledger takes such a trade
with its price and total in the money paid and a rate between the two
moneys (``costRate``), which the program works out from the price of one
share said in the asset's own money (``core/cost_rate.py``). This module
decides, for one trade, before it is checked, whether it goes this way
(the contract of 2026-11-25, part 4, items 2 to 4).

It goes this way only when all three hold; otherwise nothing changes, and
the trade goes on as it did before (asked which money, or sent as before):

1. the ledger says which money the asset is itself priced in, A
   (``AssetTable.price_money_of``; KO in USD);
2. the total's own unit names one money P the ledger prices trades in,
   and P is not A ("128欧元"); a total with no money of its own is not
   taken, and P is never read from the fee's unit;
3. P and A are not USDT and the US dollar, either way round: those two
   are never set against each other (81A, part 2, item 2).

Then the price's unit decides:

- A named ("69.5美元"): that is the price said in A;
- a vague word ("美金", "刀", "$"): it is A when the trade's own fee names
  USDT or the US dollar and that is A, or, with neither named, when the
  asset's last trade in the ledger used A (``last_money``), marked as a
  guess; when that trade used neither USDT nor the US dollar, it is A
  when A is one of the two, marked as a guess from A (2026-11-27);
  otherwise nothing changes, and A is never put in its place;
- P named ("一股64欧元"), or no price said: the user is asked the price of
  one unit in A (``AskSaidPrice``);
- another money named ("69.5 USDT" for KO), or a number with no money:
  nothing changes.

Taken, the trade's money is P, its price is left to be worked out as the
total over the quantity, and the price said in A is kept apart
(``Progress.said_prices``); a price said in P is not used. The reminders
extraction raised about the price's money for that trade are dropped,
since the two moneys were meant. A quantity not said is asked even when
the ledger takes cards: the rate cannot be worked out without it. No
amount is ever worked out across two moneys here.

Nothing here asks the ledger but through the lookup handed in, once per
asset in a passage, as for guessing a vague word; an asset that may go
this way is looked up even when its price names its money, so that its
rate can later be compared with the asset's own trades as listed.

Names defined here: ``Taken``, ``AskPrice``, ``paid_apart`` and
``said_price_of``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.followup import AskSaidPrice
from ledger_hand.core.ledger_table import VAGUE_MONEY_CODES
from ledger_hand.core.trade import InferredFrom, MoneysSaid, SaidPrice, TradeDraft
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.extraction.reply_table import Field as ReplyField
from ledger_hand.flows.guessing import own_money_to_guess
from ledger_hand.flows.last_money import LastMoney, LastMoneyLookup
from ledger_hand.flows.progress import Progress


@dataclass(frozen=True)
class Taken:
    """The trade goes this way: its draft as it now stands, and the price said apart."""

    draft: TradeDraft
    said: SaidPrice


@dataclass(frozen=True)
class AskPrice:
    """The trade would go this way, but the price of one unit in its own money was not said."""

    asked: AskSaidPrice


def said_price_of(progress: Progress, position: int) -> SaidPrice | None:
    """The price said apart for the trade at ``position``, or ``None``."""
    return dict(progress.said_prices).get(position)


def paid_apart(
    progress: Progress, position: int, draft: TradeDraft, lookup: LastMoneyLookup | None
) -> tuple[Taken | AskPrice | None, Progress]:
    """Whether the trade at ``position`` goes this way, and the progress.

    ``None`` leaves the trade as it is. The progress comes back with what
    the ledger said of the asset's trades kept, the price said apart kept
    and the reminders about the price's money dropped, when taken.
    """
    assets = progress.setting.assets
    if not assets.from_ledger or draft.coin is None:
        return None, progress
    coin = assets.find(draft.coin)
    if coin is None:
        return None, progress
    own = assets.price_money_of(coin.symbol)
    if own is None:
        return None, progress
    said = said_price_of(progress, position)
    if said is None:
        moneys = _moneys(progress, position)
        if moneys is None:
            return None, progress
        found, progress = _said(progress, draft, moneys, own, coin.symbol, lookup)
        if found is None:
            return None, progress
        if isinstance(found, str):
            unit = "share" if assets.kind_of(coin.symbol) == "stock" else coin.symbol
            asked = AskSaidPrice(money=own, paid=found, asset=coin.symbol, unit=unit)
            return AskPrice(asked), _looked_up(progress, coin.symbol, lookup)
        said = found
    elif said.money != own:
        return None, progress
    elif draft.price is not None and said.dropped is None:
        # The price asked for was answered: a price said in the money paid is not used.
        said = dataclasses.replace(said, dropped=draft.price)
    taken = dataclasses.replace(draft, quote=said.paid, price=None, derived=frozenset())
    progress = _looked_up(progress, coin.symbol, lookup)
    return Taken(taken, said), _kept(progress, position, said)


def _looked_up(progress: Progress, code: str, lookup: LastMoneyLookup | None) -> Progress:
    """The progress with the asset's trades as the ledger listed them, asked once a passage.

    A trade that goes this way, or is asked about to, is looked up even
    when its price names its money, so that its rate can be compared with
    the asset's own trades: the same answer a vague word is guessed from.
    """
    if lookup is None:
        return progress
    return _last_money(progress, code, lookup)[1]


def _moneys(progress: Progress, position: int) -> MoneysSaid | None:
    said = progress.moneys_said
    return said[position] if position < len(said) else None


def _said(
    progress: Progress,
    draft: TradeDraft,
    moneys: MoneysSaid,
    own: str,
    code: str,
    lookup: LastMoneyLookup | None,
) -> tuple[SaidPrice | str | None, Progress]:
    """The price said in ``own``; the money paid when it must be asked; or ``None``: not taken."""
    assets = progress.setting.assets
    paid = _priced_money(moneys.total, assets)
    if paid is None or paid == own or {paid, own} == VAGUE_MONEY_CODES:
        return None, progress
    if draft.price is None:
        return paid, progress
    word = moneys.price
    if word is None:
        return None, progress
    found = assets.money(word)
    if found.reading is MoneyReading.ONE:
        if found.code == own:
            return SaidPrice(amount=draft.price, money=own, paid=paid), progress
        if found.code == paid:
            return paid, progress
        return None, progress
    if found.reading is not MoneyReading.VAGUE:
        return None, progress
    meant, source, progress = _vague_meant(progress, moneys, code, own, lookup)
    if meant != own:
        return None, progress
    return SaidPrice(amount=draft.price, money=own, paid=paid, guessed_from=source), progress


def _priced_money(word: str | None, assets: AssetTable) -> str | None:
    """The code of the one money ``word`` names that the ledger prices trades in, or ``None``."""
    if word is None:
        return None
    found = assets.money(word)
    return found.code if found.reading is MoneyReading.ONE else None


def _vague_meant(
    progress: Progress,
    moneys: MoneysSaid,
    code: str,
    own: str,
    lookup: LastMoneyLookup | None,
) -> tuple[str | None, InferredFrom | None, Progress]:
    """What a vague word on the price means, by the rule of 2026-11-25, the money paid aside.

    USDT or the US dollar named on the fee first; with neither, the money
    of the asset's last trade in the ledger, when it is one of the two and
    one the ledger prices in, as a guess; when that trade used neither,
    the asset's own currency ``own``, when it is one of the two and one the
    ledger prices in, as a guess from it (the product owner's decision of 2026-11-27);
    otherwise nothing.
    """
    assets = progress.setting.assets
    named = _priced_money(moneys.fee, assets)
    if named in VAGUE_MONEY_CODES:
        return named, None, progress
    if lookup is None:
        return None, None, progress
    last, progress = _last_money(progress, code, lookup)
    found = last.found
    if found is None:
        return None, None, progress
    if found.money not in VAGUE_MONEY_CODES:
        if own_money_to_guess(assets, code) != own:
            return None, None, progress
        found = dataclasses.replace(found, own_money=own)
    if found.guessed not in assets.pricing_codes:
        return None, None, progress
    return found.guessed, found, progress


def _last_money(
    progress: Progress, code: str, lookup: LastMoneyLookup
) -> tuple[LastMoney, Progress]:
    """What the ledger says of ``code``'s last trade: kept from before, or asked now and kept."""
    for known, last in progress.last_moneys:
        if known == code:
            return last, progress
    last = lookup(code)
    kept = (*progress.last_moneys, (code, last))
    return last, dataclasses.replace(progress, last_moneys=kept)


# The reminders about the price's money that a trade taken this way no longer needs.
_MONEY_REMINDERS = frozenset({IssueKind.UNIT_NOT_THE_PRICE_CURRENCY, IssueKind.MONEY_NOT_CLEAR})


def _kept(progress: Progress, position: int, said: SaidPrice) -> Progress:
    """The progress with the price said apart kept, and the reminders about the price's money
    of this trade dropped."""
    prices = tuple(pair for pair in progress.said_prices if pair[0] != position)
    issues = tuple(
        issue
        for issue in progress.issues
        if not (
            issue.draft == position
            and issue.kind in _MONEY_REMINDERS
            and (
                issue.kind is IssueKind.UNIT_NOT_THE_PRICE_CURRENCY
                or issue.field is ReplyField.PRICE_CURRENCY
            )
        )
    )
    return dataclasses.replace(progress, said_prices=(*prices, (position, said)), issues=issues)
