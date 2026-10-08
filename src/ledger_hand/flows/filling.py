"""Putting an answer back into a trade: the cell it fills, and what it says beside it.

``fill`` puts a ``Filled`` answer into a draft: the cell takes the value
(``None`` empties it), and a currency word said with a price or a total
becomes the pricing currency, and one said with the fee becomes the fee's
coin, as the unit written with a number does in extraction. ``confirm`` puts
a yes or a no about a coin word into the coin table or the draft: yes adds
the coin to the table for the rest of this run; no empties the cell, so that
the coin is asked for again.

Names defined here: ``fill`` and ``confirm``.
"""

from __future__ import annotations

import dataclasses

from ledger_hand.core.coins import CoinTable
from ledger_hand.core.followup import Cell, ConfirmCoin, value_of, with_value
from ledger_hand.core.trade import TradeDraft
from ledger_hand.extraction.answer_phrase import Confirmation, Filled


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


def confirm(
    draft: TradeDraft, coins: CoinTable, asked: ConfirmCoin, answer: Confirmation
) -> tuple[TradeDraft, CoinTable]:
    """The draft and the coin table after a yes or a no about the coin word in ``asked.cell``."""
    word = value_of(draft, asked.cell)
    if answer is Confirmation.YES and isinstance(word, str):
        return draft, coins.with_confirmed(word)
    return with_value(draft, asked.cell, None), coins
