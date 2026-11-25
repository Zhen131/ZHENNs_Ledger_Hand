"""The word the program calls an asset by, when the asset table is the ledger's own.

The built-in coin table only ever held coins, so the program's questions
and reasons say "coin". The ledger's own list holds shares too, and the
user reads every question on the assistant page; so with a table made
from the ledger's list (``AssetTable.from_ledger``) the program picks its
word by what the trade's asset is (``word_for``):

- an asset of the table whose kind is "stock": a share (``AssetWord.SHARE``);
- one whose kind is "crypto": a coin, as before (``AssetWord.COIN``);
- an asset not recognised yet, or of another kind: an asset
  (``AssetWord.ASSET``).

The fee's asset may be money or an asset, so it is the "fee asset". The
reasons of ``validation`` that say "coin" keep their values, which the
built-in table still says word for word; ``problem_words`` gives each such
reason in words for the ledger's table instead (``LEDGER_PROBLEM_WORDS``),
and every other reason as it is. None of these words holds "币".

With the built-in table, ``word_for`` is ``None`` and ``problem_words``
gives each value unchanged: nothing said there changes by one byte.

Names defined here: ``AssetWord``, ``LEDGER_PROBLEM_WORDS``,
``LEDGER_CELL_NAMES``, ``word_for``, ``cell_name`` and ``problem_words``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping

from ledger_hand.core.assets import AssetTable
from ledger_hand.core.followup import Cell
from ledger_hand.core.validation import Missing, Violation

_STOCK = "stock"
_CRYPTO = "crypto"


class AssetWord(enum.Enum):
    """What the program calls the asset of one trade; the value is the word itself."""

    SHARE = "share"
    COIN = "coin"
    ASSET = "asset"


# Each reason whose value says "coin", in words for the ledger's own table.
LEDGER_PROBLEM_WORDS: Mapping[Missing | Violation, str] = {
    Missing.COIN: "the asset",
    Missing.COIN_CONFIRMATION: "confirmation of an asset not seen before",
    Missing.FEE_COIN: "the asset or currency the fee was paid in",
    Missing.FEE_COIN_CONFIRMATION: "confirmation of a fee asset not seen before",
    Violation.COIN_IS_USDT: "the asset traded is USDT, the pricing currency itself",
    Violation.COIN_NOT_A_SYMBOL: (
        "the ledger lists no asset by that name, and it cannot be written as a ledger symbol"
    ),
    Violation.FEE_COIN_NOT_A_SYMBOL: (
        "the ledger lists no fee asset by that name, and it cannot be written as a ledger symbol"
    ),
    Violation.FEE_NOT_BELOW_QUANTITY: (
        "a buy fee paid in the asset bought is not below the quantity"
    ),
}

# The cells whose names say "coin", named for the ledger's own table.
LEDGER_CELL_NAMES: Mapping[Cell, str] = {Cell.COIN: "asset", Cell.FEE_COIN: "fee asset"}


def word_for(assets: AssetTable, coin: str | None) -> AssetWord | None:
    """What to call the asset ``coin`` names; ``None`` with the built-in table.

    For example, with the ledger's table, "MSFT" (a stock) is a share,
    "BTC" (crypto) a coin, and "微软", not recognised, an asset.
    """
    if not assets.from_ledger:
        return None
    found = assets.find(coin) if coin is not None else None
    kind = assets.kind_of(found.symbol) if found is not None else None
    if kind == _STOCK:
        return AssetWord.SHARE
    if kind == _CRYPTO:
        return AssetWord.COIN
    return AssetWord.ASSET


def cell_name(cell: Cell, *, ledger: bool) -> str:
    """The name of ``cell`` as said: the ledger's table names the asset cells apart."""
    if ledger:
        return LEDGER_CELL_NAMES.get(cell, cell.value)
    return cell.value


def problem_words(problem: Missing | Violation, *, ledger: bool) -> str:
    """``problem`` in words: the ledger's own words for a reason that says "coin"."""
    if ledger:
        return LEDGER_PROBLEM_WORDS.get(problem, str(problem.value))
    return str(problem.value)
