"""Guessing the money a vague word meant, from the asset's last trade in the ledger.

A trade whose pricing currency, or whose fee's currency, is still a vague
word for money ("美金", "刀", "$") after extraction (``row_moneys``) is
one whose own price, total and fee named neither USDT nor the US dollar.
``guessed`` then takes the money of the asset's last trade in the ledger
(``last_money``) and marks the cell as a guess (``Inferred``), with the
trade it came from (``InferredFrom``); the user is told so when it is
sent. (The product owner's rule of 2026-11-25.)

Nothing is guessed, and the cell stays vague so that the user is asked,
when:

- no function to look with was handed in (the Record page, and every
  caller that hands none), or the table is not made from the ledger's
  list;
- the asset is not known yet, or not one of the ledger's: it is looked
  up once it is;
- extraction marked the cell as not clear (``MONEY_NOT_CLEAR``): the
  trade names two moneys of its own;
- the ledger has no trade of the asset, could not be asked, or its last
  day used two moneys;
- that money is neither USDT nor the US dollar (``VAGUE_MONEY_CODES``),
  and the asset's own currency in the ledger is not one either, or is not
  named (``own_money_to_guess``);
- the money taken is not one the ledger prices trades in now.

When the last trade's money is neither USDT nor the US dollar (KO last
bought for euros), the asset's own currency is taken instead when the
ledger names it and it is USDT or the US dollar (KO priced in USD), marked
as a guess from it, the last trade still named (``InferredFrom.own_money``;
the product owner's decision of 2026-11-27 on "美金"). Only then:
with no trade, a failure, or two moneys on the last day, nothing is guessed
as before.

A fee's currency is guessed only for a fee above zero; a fee of zero is
recorded in the trade's own money.

Example: "花了30美金买了ETH，均价2400" with ETH last bought for USDT gives
a trade priced in USDT, marked as a guess from that trade.

Each asset is looked up at most once in a passage: what the ledger said
is kept in ``Progress.last_moneys``.

Names defined here: ``guessed`` and ``own_money_to_guess``.
"""

from __future__ import annotations

import dataclasses

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.ledger_table import VAGUE_MONEY_CODES
from ledger_hand.core.trade import Inferred, TradeDraft
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.extraction.reply_table import Field
from ledger_hand.flows.last_money import LastMoney, LastMoneyLookup
from ledger_hand.flows.progress import Progress


def guessed(
    progress: Progress, position: int, draft: TradeDraft, lookup: LastMoneyLookup | None
) -> tuple[TradeDraft, Progress]:
    """The draft at ``position`` with its vague moneys guessed where they may be, and the progress.

    The progress comes back with what the ledger said kept; the draft is
    not put into it here.
    """
    assets = progress.setting.assets
    if lookup is None or not assets.from_ledger:
        return draft, progress
    cells = _vague_cells(progress, position, draft, assets)
    coin = assets.find(draft.coin) if draft.coin is not None else None
    if not cells or coin is None:
        return draft, progress
    last, progress = _last_money(progress, coin.symbol, lookup)
    found = last.found
    if found is None:
        return draft, progress
    if found.money not in VAGUE_MONEY_CODES:
        own = own_money_to_guess(assets, coin.symbol)
        if own is None:
            return draft, progress
        found = dataclasses.replace(found, own_money=own)
    money = found.guessed
    if money not in assets.pricing_codes:
        return draft, progress
    draft = dataclasses.replace(
        draft,
        quote=money if Inferred.QUOTE in cells else draft.quote,
        fee_coin=money if Inferred.FEE_COIN in cells else draft.fee_coin,
        inferred=draft.inferred | cells,
        inferred_from=found,
    )
    return draft, progress


def own_money_to_guess(assets: AssetTable, code: str) -> str | None:
    """The asset's own currency, when a vague word may be taken as it; ``None`` otherwise.

    Only when the ledger names it, it is USDT or the US dollar, and the
    ledger prices trades in it now. Example: KO priced in USD gives "USD";
    DOT priced in EUR, or ADA with no currency named, gives ``None``.
    """
    own = assets.price_money_of(code)
    if own is None or own not in VAGUE_MONEY_CODES or own not in assets.pricing_codes:
        return None
    return own


def _vague_cells(
    progress: Progress, position: int, draft: TradeDraft, assets: AssetTable
) -> frozenset[Inferred]:
    """The cells of the draft that hold a vague word and may be guessed."""
    cells: set[Inferred] = set()
    if _is_vague(draft.quote, assets) and not _not_clear(progress, position, Field.PRICE_CURRENCY):
        cells.add(Inferred.QUOTE)
    fee_above_zero = draft.fee is not None and not draft.fee.is_zero()
    if (
        fee_above_zero
        and _is_vague(draft.fee_coin, assets)
        and not _not_clear(progress, position, Field.FEE_CURRENCY)
    ):
        cells.add(Inferred.FEE_COIN)
    return frozenset(cells)


def _is_vague(word: str | None, assets: AssetTable) -> bool:
    return word is not None and assets.money(word).reading is MoneyReading.VAGUE


def _not_clear(progress: Progress, position: int, field: Field) -> bool:
    """Whether extraction marked this cell of the draft as naming two moneys: asked, not guessed."""
    return any(
        issue.kind is IssueKind.MONEY_NOT_CLEAR and issue.draft == position and issue.field is field
        for issue in progress.issues
    )


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
