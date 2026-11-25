"""Whether the asset and the side the model gave a read tool are ones the user asked for.

The model fills a lookup's ``asset`` and ``side`` itself. Copied word for
word they would often be refused ("BTC" for the user's "比特币"), and taken
as they stand they could narrow a lookup the user never narrowed. So for
the two read tools that take them (``list_trades``, ``get_period_summary``)
the program checks them against what the user said, and uses one only when
the user said it; otherwise the lookup is not narrowed by it, and the
header says so. Neither is a wrong step. (Decided on 2026-11-24.)

The asset, in four steps:

1. The ways an asset of the ledger is named: its code and its name, letter
   case aside, and the other names the coin table gives the coin with that
   code ("比特币" and "大饼" for BTC). The coin table's names count only for
   a code the ledger has.
2. Finding them in what the user said: a name in Latin letters or digits is
   found only as a whole word, with no letter or digit beside it ("ETH" is
   not in "something"); longer names are found first, and a shorter one
   inside a longer one does not count ("比特币" is not found in "比特币现金").
   Every coin in the coin table takes part in this, so that a longer name
   of a coin the ledger lacks still covers the shorter one. Both kinds of
   name come from one place, the names the ledger's list makes
   (``ledger_table.names_of``), which recording uses too. Words for money
   ("U", "刀") are not among them.
3. The model's word names an asset of the ledger: it is used when the user
   named that asset in what they said just now, or, when they named no
   asset just now, in what they said the time before ("那上个月呢"). Any
   other way it is dropped (``AssetDropped``).
4. The model's word names no asset of the ledger: when it looks like a code
   (2 to 10 letters or digits, one letter at least) and the user said it,
   as a whole word, just now, the ledger has no such asset
   (``NoSuchAsset``); the program says so and asks nothing of the ledger.
   Any other word ("币", "coin", "crypto", or one the user never said) is
   dropped; a few English words for coins or assets in general look like
   a code and are listed so as never to be taken for one.

The side: only the fixed words for a buy and a sell of
``extraction.answer_words`` count. Words that name both sides together
("买卖", "buy and sell") are taken out first; English words are found as
whole words. The side is used when only words of that side are left, or,
as with the asset, when what the user said just now names no side at all
and what they said the time before names only that side ("那ETH呢" after
"10月我卖了哪些BTC"); otherwise it is dropped (``SideDropped``).

Names defined here: ``AssetUsed``, ``AssetDropped``, ``NoSuchAsset``,
``SideUsed``, ``SideDropped``, ``check_asset``, ``check_side`` and
``assets_named``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ledger_hand.core.ledger_records import Asset
from ledger_hand.core.ledger_table import names_of
from ledger_hand.core.trade import Side
from ledger_hand.extraction.answer_words import SIDE_WORDS


@dataclass(frozen=True)
class AssetUsed:
    """The lookup is narrowed to the asset with this code."""

    code: str


@dataclass(frozen=True)
class AssetDropped:
    """The model's word is not used, and why, in one sentence for the header."""

    given: str
    why: str


@dataclass(frozen=True)
class NoSuchAsset:
    """The user named an asset the ledger does not have: the word they said."""

    word: str


@dataclass(frozen=True)
class SideUsed:
    """The lookup is narrowed to this side."""

    side: Side


@dataclass(frozen=True)
class SideDropped:
    """The model's side is not used, and why, in one sentence for the header."""

    given: str
    why: str


# Words for coins or assets in general, never a code, though some look like one.
_GENERAL_WORDS = frozenset(
    {
        "coin",
        "coins",
        "crypto",
        "cryptos",
        "token",
        "tokens",
        "asset",
        "assets",
        "stock",
        "stocks",
        "money",
        "currency",
        "all",
    }
)
_MASK = "\x00"
_LATIN = re.compile(r"[a-z0-9 .\-]+")
_LIKE_A_CODE = re.compile(r"[A-Za-z0-9]{2,10}")


def _plain(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _forms(assets: Sequence[Asset]) -> Mapping[str, str]:
    """Every name of every known asset or coin, in plain form, to the code it names.

    The names are those the asset table made of the ledger's list gives
    (``ledger_table.names_of``): what the ledger's assets go by, and the
    names that only cover. The ledger's own codes and names come last, so
    they win over the coin table's where both claim one.
    """
    forms: dict[str, str] = {}
    for form, code in names_of(assets).in_lookup_order():
        forms[_plain(form)] = code
    return forms


def _found_codes(text: str, forms: Mapping[str, str]) -> list[str]:
    """The codes named in ``text``, longest names first, each covering what it holds."""
    left = _plain(text)
    found: list[str] = []
    for form in sorted(forms, key=len, reverse=True):
        pattern = re.escape(form)
        if _LATIN.fullmatch(form):
            pattern = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
        hits = list(re.finditer(pattern, left))
        if hits:
            found.append(forms[form])
            for hit in hits:
                left = left[: hit.start()] + _MASK * len(hit.group()) + left[hit.end() :]
    return found


def assets_named(text: str, assets: Sequence[Asset]) -> frozenset[str]:
    """The codes of the ledger's assets that ``text`` names."""
    codes = {asset.code for asset in assets}
    return frozenset(code for code in _found_codes(text, _forms(assets)) if code in codes)


def _ledger_code(given: str, assets: Sequence[Asset]) -> str | None:
    """The code of the ledger's asset the model's word names, if it names one."""
    codes = {asset.code for asset in assets}
    code = _forms(assets).get(_plain(given))
    return code if code in codes else None


def check_asset(
    given: str, assets: Sequence[Asset], said_now: str, said_before: str | None
) -> AssetUsed | AssetDropped | NoSuchAsset:
    """Whether to narrow a lookup to the asset the model gave, ``given``."""
    code = _ledger_code(given, assets)
    if code is None:
        word = given.strip()
        like_a_code = (
            bool(_LIKE_A_CODE.fullmatch(word))
            and any(c.isalpha() for c in word)
            and _plain(word) not in _GENERAL_WORDS
        )
        if like_a_code and word.casefold() in _whole_words(said_now):
            return NoSuchAsset(word=word)
        return AssetDropped(given=given, why=f"Not narrowed to {given!r}: it names no asset.")
    if code in assets_named(said_now, assets):
        return AssetUsed(code=code)
    named_now = _found_codes(said_now, _forms(assets))
    if not named_now and said_before is not None and code in assets_named(said_before, assets):
        return AssetUsed(code=code)
    return AssetDropped(given=given, why=f"Not narrowed to {code}: you did not name it.")


def _whole_words(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", _plain(text)))


# Words that name both sides at once; taken out before the side is looked for.
_BOTH_SIDES = (
    "买入卖出",
    "买进卖出",
    "卖出买入",
    "买卖",
    "buying and selling",
    "buys and sells",
    "bought and sold",
    "buy and sell",
    "sell and buy",
)


def _sides_said(text: str, words: Iterable[tuple[str, Side]]) -> frozenset[Side]:
    left = _plain(text)
    for both in _BOTH_SIDES:
        left = left.replace(both, _MASK)
    sides: set[Side] = set()
    for word, side in words:
        pattern = re.escape(word)
        if word.isascii():
            pattern = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
        if re.search(pattern, left):
            sides.add(side)
    return frozenset(sides)


def check_side(given: str, said_now: str, said_before: str | None = None) -> SideUsed | SideDropped:
    """Whether to narrow a list of trades to the side the model chose, ``given``.

    ``said_before`` is what the user said the time before in this chat; its
    side is kept only when nothing said just now names a side at all.
    """
    side = Side(given)
    said = _sides_said(said_now, SIDE_WORDS.items())
    if said == {side}:
        return SideUsed(side=side)
    said_then = _sides_said(said_before, SIDE_WORDS.items()) if said_before else frozenset()
    if not said and said_then == {side}:
        return SideUsed(side=side)
    return SideDropped(
        given=given,
        why=f"Not narrowed to {side.value}s: what you said does not name {side.value}s alone.",
    )
