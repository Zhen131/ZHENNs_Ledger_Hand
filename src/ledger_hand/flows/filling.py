"""Putting an answer back into a trade: the cell it fills, and what it says beside it.

``fill`` puts a ``Filled`` answer into a draft: the cell takes the value
(``None`` empties it), and a currency word said with a price or a total
becomes the pricing currency, and one said with the fee becomes the fee's
coin, as the unit written with a number does in extraction; the answer to
which currency the trade was priced in fills that cell. ``confirm`` puts a
yes or a no about a coin word into the asset table or the draft: yes adds
the coin to the table for the rest of this run; no empties the cell, so that
the coin is asked for again.

``fill_from_ledger`` does what ``fill`` does for a table made from the
ledger's list, with one more rule for a word for money said with a price,
a total or a fee (decided on 2026-11-25, so that an answer never quietly
changes the trade's money):

- a money named outright that is the trade's own money (or its fee's)
  fills the number; when the program had guessed that money, the guess
  mark goes, since the user has now said it;
- a money named outright that is not the trade's own fills nothing: a
  ``MoneyClash`` comes back, and the user is asked which money it is
  (``settle_clash`` then puts the answer in);
- a vague word ("刀") fills the number and follows the money the trade
  has; when the trade has none yet, its money is still asked, never
  guessed;
- an answer to which money the trade (or its fee) was in takes away that
  cell's guess mark.

With the built-in table, ``fill`` is used as before.

Names defined here: ``fill``, ``fill_from_ledger``, ``settle_clash`` and
``confirm``.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.followup import AMOUNT_CELLS, Cell, ConfirmCoin, value_of, with_value
from ledger_hand.core.trade import Amount, Inferred, TradeDraft
from ledger_hand.extraction.answer_phrase import Confirmation, Filled
from ledger_hand.extraction.unit_currency import word_identity
from ledger_hand.flows.progress import MoneyClash

# The cell a word for money said with an amount speaks for, and its guess mark.
_MONEY_CELL = {
    Cell.PRICE: (Cell.QUOTE, Inferred.QUOTE),
    Cell.TOTAL: (Cell.QUOTE, Inferred.QUOTE),
    Cell.FEE: (Cell.FEE_COIN, Inferred.FEE_COIN),
}
_MARK_OF = {Cell.QUOTE: Inferred.QUOTE, Cell.FEE_COIN: Inferred.FEE_COIN}
_AMOUNT_OF = {Cell.QUANTITY: Amount.QUANTITY, Cell.PRICE: Amount.PRICE, Cell.TOTAL: Amount.TOTAL}


def fill(draft: TradeDraft, answer: Filled) -> TradeDraft:
    """``draft`` with the answer put in."""
    draft = with_value(draft, answer.cell, answer.value)
    if answer.unit is None:
        return draft
    if answer.cell in (Cell.PRICE, Cell.TOTAL):
        return dataclasses.replace(draft, quote=answer.unit)
    if answer.cell is Cell.FEE:
        return with_value(draft, Cell.FEE_COIN, answer.unit)
    return draft


def fill_from_ledger(
    draft: TradeDraft, answer: Filled, assets: AssetTable, trade: int
) -> TradeDraft | MoneyClash:
    """``draft`` with the answer put in, or the clash when its money is not the trade's.

    ``trade`` is the trade's position, counting from 0, kept in the clash.
    """
    if answer.cell in _MARK_OF:
        return _unmarked(fill(draft, answer), _MARK_OF[answer.cell])
    if (
        answer.unit is None
        or answer.cell not in _MONEY_CELL
        or not isinstance(answer.value, Decimal)
    ):
        return fill(draft, answer)
    target, mark = _MONEY_CELL[answer.cell]
    current = value_of(draft, target)
    settled = isinstance(current, str) and not _is_vague(current, assets)
    if _is_vague(answer.unit, assets):
        return with_value(draft, answer.cell, answer.value)
    if not settled or not isinstance(current, str):
        return fill(draft, answer)
    said = word_identity(answer.unit, assets)
    before = word_identity(current, assets)
    if said == before:
        return _unmarked(with_value(draft, answer.cell, answer.value), mark)
    return MoneyClash(
        trade=trade,
        cell=answer.cell,
        value=answer.value,
        said=answer.unit,
        said_code=said,
        before=before,
        guessed=mark in draft.inferred,
    )


def settle_clash(
    draft: TradeDraft, clash: MoneyClash, chosen: str, assets: AssetTable
) -> TradeDraft:
    """``draft`` once the user said which money a clash was in; ``chosen`` is the word answered.

    The answered money takes the cell, and the guess mark goes. When it is
    the money of the clash's answer, that number is filled in; any other
    price or total said before in the trade's earlier money, when that
    money was said and not guessed, is emptied, to be asked again. When it
    is the earlier money, the clash's number is not filled, and is asked
    again.
    """
    target, mark = _MONEY_CELL[clash.cell]
    draft = _unmarked(with_value(draft, target, chosen), mark)
    if word_identity(chosen, assets) != clash.said_code:
        return draft
    draft = with_value(draft, clash.cell, clash.value)
    if target is Cell.QUOTE and not clash.guessed:
        for cell in AMOUNT_CELLS:
            if cell not in (Cell.QUANTITY, clash.cell) and value_of(draft, cell) is not None:
                draft = _emptied(draft, cell)
    return draft


def _emptied(draft: TradeDraft, cell: Cell) -> TradeDraft:
    """``draft`` with the amount ``cell`` emptied, no longer marked as worked out."""
    draft = with_value(draft, cell, None)
    return dataclasses.replace(draft, derived=draft.derived - {_AMOUNT_OF[cell]})


def _unmarked(draft: TradeDraft, mark: Inferred) -> TradeDraft:
    """``draft`` without the guess ``mark``; with no mark left, no trade it came from either."""
    if mark not in draft.inferred:
        return draft
    left = draft.inferred - {mark}
    source = draft.inferred_from if left else None
    return dataclasses.replace(draft, inferred=left, inferred_from=source)


def _is_vague(word: str, assets: AssetTable) -> bool:
    return assets.money(word).reading is MoneyReading.VAGUE


def confirm(
    draft: TradeDraft, assets: AssetTable, asked: ConfirmCoin, answer: Confirmation
) -> tuple[TradeDraft, AssetTable]:
    """The draft and the asset table after a yes or a no about the coin word in ``asked.cell``."""
    word = value_of(draft, asked.cell)
    if answer is Confirmation.YES and isinstance(word, str):
        return draft, assets.with_confirmed(word)
    return with_value(draft, asked.cell, None), assets
