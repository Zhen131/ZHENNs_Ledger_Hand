"""Which money a row means when it says a vague word for money ("美金", "刀", "$").

A vague word may mean USDT or the US dollar, and the asset table never
reads it as either by itself. This module settles, for one row of the
model's table, what its pricing currency and its fee's currency cells
hold when a vague word is among them, by the product owner's rule of
2026-11-25:

1. The row itself names a money outright. Only the units written with the
   row's own price, total and fee count ("2400 USDT", "手续费1美元"); the
   two currency cells do not, since the model may copy them from anywhere
   in the passage, and neither does any other part of the passage. A fee
   taken in a coin ("0.0002个ETH") names no money. When the row names
   exactly one of USDT and the US dollar, every vague word of the row
   means that one, with no reminder.
2. The row names neither: the vague word stays in its cell, and the
   recording flow guesses the money from the asset's last trade in the
   ledger, or asks (``flows.last_money``).
3. The row names both, or names another money beside the vague word: the
   vague word stays in its cell and is marked ``MONEY_NOT_CLEAR``, so that
   the user is asked which money and nothing is guessed. A money the
   ledger lacks, or prices nothing in, named on the price or the total
   goes into the cell instead, so that the trade is told it cannot be
   recorded.

Example: "花了30美金买ETH，成交均价2400 USDT" makes the price's unit USDT,
so the pricing currency is USDT and the total of 30 is 30 USDT.

Only a table made from the ledger's list has vague words, so with any
other table ``says_vague_money`` is false and the row is read as before.

Names defined here: ``says_vague_money`` and ``settle_moneys``.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.ledger_table import VAGUE_MONEY_CODES
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import CurrencyWord, currencies_in_unit, word_identity

_PRICED = (Field.PRICE, Field.TOTAL)

type Note = tuple[IssueKind, Field, str]


@dataclass(frozen=True)
class _Said:
    """The currency words of one unit, sorted: vague ones, money named outright, coins."""

    vague: tuple[CurrencyWord, ...]
    money: tuple[CurrencyWord, ...]
    other: tuple[CurrencyWord, ...]


def says_vague_money(
    units: Mapping[Field, str],
    texts: Mapping[Field, str],
    assets: AssetTable,
    allowed: tuple[str, ...],
) -> bool:
    """Whether a vague word for money stands in the row's units or its two currency cells."""
    if not assets.from_ledger:
        return False
    cells = (texts.get(Field.PRICE_CURRENCY), texts.get(Field.FEE_CURRENCY))
    if any(text is not None and _is_vague(text, assets) for text in cells):
        return True
    return any(
        _sorted(unit, assets, allowed).vague
        for name, unit in units.items()
        if name is not Field.QUANTITY
    )


def settle_moneys(
    units: Mapping[Field, str],
    texts: MutableMapping[Field, str],
    assets: AssetTable,
    allowed: tuple[str, ...],
) -> tuple[Note, ...]:
    """Fill the row's two currency cells in ``texts`` by the rule above; the notes it raises."""
    said = {
        name: _sorted(unit, assets, allowed)
        for name, unit in units.items()
        if name is not Field.QUANTITY
    }
    outright = _outright(said)
    notes: list[Note] = []
    notes.extend(_settle_quote(said, outright, texts, assets))
    notes.extend(_settle_fee(said, outright, texts, assets))
    return tuple(notes)


def _outright(said: Mapping[Field, _Said]) -> dict[str, CurrencyWord]:
    """USDT or the US dollar, as the row's own price, total and fee name them outright."""
    found: dict[str, CurrencyWord] = {}
    for name in (*_PRICED, Field.FEE):
        for word in said[name].money if name in said else ():
            if word.identity in VAGUE_MONEY_CODES and word.identity not in found:
                found[word.identity] = word
    return found


def _settle_quote(
    said: Mapping[Field, _Said],
    outright: Mapping[str, CurrencyWord],
    texts: MutableMapping[Field, str],
    assets: AssetTable,
) -> list[Note]:
    vague = [word for name in _PRICED if name in said for word in said[name].vague]
    named = [
        word for name in _PRICED if name in said for word in (*said[name].money, *said[name].other)
    ]
    codes = {word.identity for word in named}
    if not vague and not named:
        current = texts.get(Field.PRICE_CURRENCY)
        if current is None or not _is_vague(current, assets):
            return []
        if len(outright) == 1:
            texts[Field.PRICE_CURRENCY] = next(iter(outright.values())).text
        elif outright:
            return [(IssueKind.MONEY_NOT_CLEAR, Field.PRICE_CURRENCY, current)]
        return []
    if not vague:
        return _named_only(named, texts, assets)
    if len(outright) == 1 and codes <= set(outright):
        texts[Field.PRICE_CURRENCY] = next(iter(outright.values())).text
        return []
    if not outright and not named:
        texts[Field.PRICE_CURRENCY] = vague[0].text
        return []
    blocked = [word for word in named if _cannot_be_used(word.text, assets)]
    if blocked:
        texts[Field.PRICE_CURRENCY] = blocked[0].text
        return []
    texts[Field.PRICE_CURRENCY] = vague[0].text
    return [(IssueKind.MONEY_NOT_CLEAR, Field.PRICE_CURRENCY, vague[0].text)]


def _named_only(
    named: list[CurrencyWord], texts: MutableMapping[Field, str], assets: AssetTable
) -> list[Note]:
    """The price and total name currencies outright, and no vague word: as the row says.

    One currency fills the cell. Two are both noted; one the ledger lacks
    or prices nothing in goes into the cell, so the trade is told so, and
    otherwise the cell is emptied, so that the user is asked.
    """
    first = named[0]
    if all(word.identity == first.identity for word in named):
        texts[Field.PRICE_CURRENCY] = first.text
        return []
    notes = [
        (IssueKind.UNIT_NOT_THE_PRICE_CURRENCY, Field.PRICE_CURRENCY, word.text)
        for word in named[1:]
    ]
    blocked = [word for word in named if _cannot_be_used(word.text, assets)]
    if blocked:
        texts[Field.PRICE_CURRENCY] = blocked[0].text
    else:
        texts.pop(Field.PRICE_CURRENCY, None)
    return notes


def _settle_fee(
    said: Mapping[Field, _Said],
    outright: Mapping[str, CurrencyWord],
    texts: MutableMapping[Field, str],
    assets: AssetTable,
) -> list[Note]:
    fee = said.get(Field.FEE)
    current = texts.get(Field.FEE_CURRENCY)
    if fee is not None and (fee.money or fee.other):
        word = (*fee.money, *fee.other)[0]
        if current is None or _is_vague(current, assets):
            texts[Field.FEE_CURRENCY] = word.text
            return []
        if word_identity(current, assets) != word.identity:
            return [(IssueKind.UNIT_NOT_THE_FEE_CURRENCY, Field.FEE, word.text)]
        return []
    vague = fee.vague[0].text if fee is not None and fee.vague else None
    if vague is None and current is not None and _is_vague(current, assets):
        vague = current
    if vague is None:
        return []
    if len(outright) == 1:
        texts[Field.FEE_CURRENCY] = next(iter(outright.values())).text
        return []
    texts[Field.FEE_CURRENCY] = vague
    if outright:
        return [(IssueKind.MONEY_NOT_CLEAR, Field.FEE_CURRENCY, vague)]
    return []


def _sorted(unit: str, assets: AssetTable, allowed: tuple[str, ...]) -> _Said:
    vague: list[CurrencyWord] = []
    money: list[CurrencyWord] = []
    other: list[CurrencyWord] = []
    for word in currencies_in_unit(unit, assets, allowed):
        reading = assets.money(word.text).reading
        if reading is MoneyReading.VAGUE:
            vague.append(word)
        elif reading is not MoneyReading.NOT_MONEY or assets.missing_money(word.text):
            money.append(word)
        else:
            other.append(word)
    return _Said(tuple(vague), tuple(money), tuple(other))


def _is_vague(text: str, assets: AssetTable) -> bool:
    return assets.money(text).reading is MoneyReading.VAGUE


def _cannot_be_used(text: str, assets: AssetTable) -> bool:
    """Whether ``text`` names a money the ledger lacks or prices no trade in."""
    reading = assets.money(text).reading
    return reading is MoneyReading.CANNOT_PRICE or assets.missing_money(text) is not None
