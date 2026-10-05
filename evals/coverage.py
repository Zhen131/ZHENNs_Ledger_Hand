"""What the test sentences cover: every item the test set must have, worked out per sentence.

``items_of`` gives the coverage items of one sentence. Most are read off the
gold answer itself, so they cannot be labelled wrongly:

- the language, and how many trades the passage holds (none, for talk);
- what is missing: a field the passage does not say (the price, the fee,
  the time, the coin), and passages that say only one of quantity, price
  and total;
- which two of quantity, price and total are said;
- the fee: zero, in USDT, in the trade's own coin, in a third coin;
- buy and sell; an opinion; a platform;
- a field the passage says but the rules leave empty (a number or time the
  core is unsure of);
- the kind of a passage the ledger does not take.

The rest come from the sentence's hand-given ``features`` (how numbers and
times are written, a number that belongs to no trade, a detail shared by
several trades). ``feature_holds`` checks each such label against the
sentence, so a label cannot be given where the sentence does not bear it out.

A passage the ledger does not take counts only for its language and its
kind: it has no gold trades.

Names defined here: ``Item``, ``items_of``, ``feature_holds`` and
``coverage_table``.
"""

from __future__ import annotations

import collections
import enum
import re
from collections.abc import Iterable, Mapping
from decimal import Decimal

from evals.gold import Feature, GoldTrade, Group, Language, NotToRecord, Sentence, Split
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.trade import Side, TimePrecision
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import word_identity


class Item(enum.Enum):
    """One thing the test set must cover; the value names it in the coverage table."""

    CHINESE = "language: Chinese"
    ENGLISH = "language: English"
    MIXED = "language: Chinese and English mixed"
    ONE_TRADE = "trades: one"
    TWO_TRADES = "trades: two"
    THREE_OR_MORE = "trades: three or more"
    NO_TRADE = "trades: none (talk)"
    NO_PRICE = "missing: price"
    NO_FEE = "missing: fee"
    NO_TIME = "missing: time"
    NO_COIN = "missing: coin"
    ONE_AMOUNT = "missing: only one of quantity, price, total said"
    QUANTITY_AND_PRICE = "two of three: quantity and price"
    QUANTITY_AND_TOTAL = "two of three: quantity and total"
    PRICE_AND_TOTAL = "two of three: price and total"
    CHINESE_NUMERALS = "numbers: Chinese numerals"
    MULTIPLIER = "numbers: digits with a multiplier (k, w, 千, 万)"
    THOUSANDS_COMMA = "numbers: thousands comma"
    CURRENCY_WORD = "numbers: with a currency word"
    PER_PIECE = "numbers: so much a piece (3000一个)"
    GAP_BEFORE_MULTIPLIER = "numbers: a gap before the multiplier (3 w, 100 万)"
    SPACE_THOUSANDS = "numbers: a space between thousands (94 900)"
    ADJACENT_NUMBERS = "numbers: two numbers one space apart (0.02 94900)"
    SPAN_BACK = "time: a span back (3 小时前)"
    DAY_WORD_WITH_CLOCK = "time: a day word with a clock time"
    WRITTEN_DATE = "time: a written date"
    DATE_ONLY = "time: a day only"
    TIME_NOT_SAID = "time: not said"
    FEE_ZERO = "fee: zero"
    FEE_USDT = "fee: in USDT"
    FEE_OWN_COIN = "fee: in the trade's own coin"
    FEE_THIRD_COIN = "fee: in a third coin"
    BUY = "side: buy"
    SELL = "side: sell"
    UNRELATED_NUMBER = "distraction: a number that belongs to no trade"
    OPINION = "distraction: an opinion"
    PLATFORM = "distraction: a platform"
    SHARED_DETAIL = "several trades sharing a detail"
    RULES_LEAVE_EMPTY = "said, but the rules leave the field empty"
    FUTURES = "not to record: futures or leverage"
    COIN_FOR_COIN = "not to record: a coin paid with another coin"
    OPEN_ORDER = "not to record: an order not filled yet"
    PLAN = "not to record: a plan"


_LANGUAGE = {
    Language.CHINESE: Item.CHINESE,
    Language.ENGLISH: Item.ENGLISH,
    Language.MIXED: Item.MIXED,
}
_KIND = {
    NotToRecord.FUTURES: Item.FUTURES,
    NotToRecord.COIN_FOR_COIN: Item.COIN_FOR_COIN,
    NotToRecord.OPEN_ORDER: Item.OPEN_ORDER,
    NotToRecord.PLAN: Item.PLAN,
}
_FEATURE = {feature: Item[feature.name] for feature in Feature}
_AMOUNTS = (Field.QUANTITY, Field.PRICE, Field.TOTAL)
_TWO_OF_THREE = {
    frozenset({Field.QUANTITY, Field.PRICE}): Item.QUANTITY_AND_PRICE,
    frozenset({Field.QUANTITY, Field.TOTAL}): Item.QUANTITY_AND_TOTAL,
    frozenset({Field.PRICE, Field.TOTAL}): Item.PRICE_AND_TOTAL,
}
_NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)


def items_of(sentence: Sentence) -> frozenset[Item]:
    """The coverage items of ``sentence``."""
    items = {_LANGUAGE[sentence.language]}
    if sentence.group is Group.NOT_TO_RECORD:
        if sentence.kind is not None:
            items.add(_KIND[sentence.kind])
        return frozenset(items)
    items.add(_count_item(len(sentence.trades)))
    for trade in sentence.trades:
        items.update(_trade_items(trade))
    items.update(_FEATURE[feature] for feature in sentence.features)
    return frozenset(items)


def _count_item(count: int) -> Item:
    if count == 0:
        return Item.NO_TRADE
    if count == 1:
        return Item.ONE_TRADE
    return Item.TWO_TRADES if count == 2 else Item.THREE_OR_MORE


def _said(trade: GoldTrade, field: Field) -> bool:
    return trade.cell(field).phrase is not None


def _missing_items(trade: GoldTrade) -> set[Item]:
    items: set[Item] = set()
    for field, item in (
        (Field.PRICE, Item.NO_PRICE),
        (Field.FEE, Item.NO_FEE),
        (Field.TIME, Item.NO_TIME),
        (Field.COIN, Item.NO_COIN),
    ):
        if not _said(trade, field):
            items.add(item)
    if not _said(trade, Field.TIME):
        items.add(Item.TIME_NOT_SAID)
    said = frozenset(field for field in _AMOUNTS if _said(trade, field))
    if len(said) == 1:
        items.add(Item.ONE_AMOUNT)
    if said in _TWO_OF_THREE:
        items.add(_TWO_OF_THREE[said])
    return items


def _trade_items(trade: GoldTrade) -> set[Item]:
    items = _missing_items(trade)
    fee_item = _fee_item(trade)
    if fee_item is not None:
        items.add(fee_item)
    side = trade.value(Field.SIDE)
    if isinstance(side, Side):
        items.add(Item.BUY if side is Side.BUY else Item.SELL)
    if _said(trade, Field.OPINION):
        items.add(Item.OPINION)
    if _said(trade, Field.PLATFORM):
        items.add(Item.PLATFORM)
    if any(cell.phrase is not None and cell.value is None for cell in trade.cells.values()):
        items.add(Item.RULES_LEAVE_EMPTY)
    return items


def _fee_item(trade: GoldTrade) -> Item | None:
    fee = trade.value(Field.FEE)
    if not isinstance(fee, Decimal):
        return None
    if fee == 0:
        return Item.FEE_ZERO
    currency = trade.value(Field.FEE_CURRENCY)
    if not isinstance(currency, str):
        return None
    named = word_identity(currency, BUILT_IN_TABLE)
    coin = trade.value(Field.COIN)
    if named == "USDT":
        return Item.FEE_USDT
    if isinstance(coin, str) and named == word_identity(coin, BUILT_IN_TABLE):
        return Item.FEE_OWN_COIN
    return Item.FEE_THIRD_COIN


# --- checking the hand-given labels ---------------------------------------------

_CHINESE_DIGITS = re.compile(r"[一二两三四五六七八九十]")
_MULTIPLIED = re.compile(r"\d\s*(?:[kKwW](?![A-Za-z])|千|万|亿)")
_GAPPED_MULTIPLIER = re.compile(r"\d\s+(?:[kKwW](?![A-Za-z])|千|万|亿)")
_COMMA_GROUPS = re.compile(r"\d{1,3}(?:,\d{3})+")
_SPACE_GROUPS = re.compile(r"\d{1,3} \d{3}(?!\d)")
_PER_PIECE = re.compile(r"\d一[个枚]")
_SPAN = re.compile(r"前$|ago$")
_WRITTEN_DATE = re.compile(
    r"\d\s*月|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)|\d{4}-\d"
)
_USDT_UNIT = re.compile(r"(?:U|USDT|刀|美元|美金|\$)\s*$", re.IGNORECASE)


def _number_phrases(sentence: Sentence, fields: Iterable[Field] = _NUMBER_FIELDS) -> list[str]:
    wanted = tuple(fields)
    return [
        phrase
        for trade in sentence.trades
        for field in wanted
        if (phrase := trade.cell(field).phrase) is not None
    ]


def _times(sentence: Sentence) -> list[tuple[str, TimePrecision | None]]:
    found: list[tuple[str, TimePrecision | None]] = []
    for trade in sentence.trades:
        cell = trade.cell(Field.TIME)
        if cell.phrase is not None:
            value = cell.value
            precision = getattr(value, "precision", None)
            found.append((cell.phrase, precision))
    return found


def _has_unrelated_number(sentence: Sentence) -> bool:
    """Whether a digit is left in the text once every gold phrase is taken out of it."""
    rest = sentence.text
    phrases = {cell.phrase for t in sentence.trades for cell in t.cells.values() if cell.phrase}
    for phrase in sorted(phrases, key=len, reverse=True):
        rest = rest.replace(phrase, " ")
    return any(character.isdigit() for character in rest)


def _shares_a_detail(sentence: Sentence) -> bool:
    if len(sentence.trades) < 2:
        return False
    for field in Field:
        if field is Field.SIDE:
            continue
        phrases = [trade.cell(field).phrase for trade in sentence.trades]
        said = [phrase for phrase in phrases if phrase is not None]
        if len(said) != len(set(said)):
            return True
    return False


def _adjacent(sentence: Sentence) -> bool:
    for trade in sentence.trades:
        quantity = trade.cell(Field.QUANTITY).phrase
        price = trade.cell(Field.PRICE).phrase
        if quantity and price and f"{quantity} {price}" in sentence.text:
            return True
    return False


def _checks(sentence: Sentence) -> Mapping[Feature, bool]:
    numbers = _number_phrases(sentence)
    money = _number_phrases(sentence, (Field.PRICE, Field.TOTAL, Field.FEE))
    times = _times(sentence)
    return {
        Feature.CHINESE_NUMERALS: any(_CHINESE_DIGITS.search(p) for p in numbers),
        Feature.MULTIPLIER: any(_MULTIPLIED.search(p) for p in numbers),
        Feature.THOUSANDS_COMMA: any(_COMMA_GROUPS.search(p) for p in numbers),
        Feature.CURRENCY_WORD: any(_USDT_UNIT.search(p) for p in money),
        Feature.PER_PIECE: _PER_PIECE.search(sentence.text) is not None,
        Feature.GAP_BEFORE_MULTIPLIER: any(_GAPPED_MULTIPLIER.search(p) for p in numbers),
        Feature.SPACE_THOUSANDS: any(_SPACE_GROUPS.search(p) for p in numbers),
        Feature.ADJACENT_NUMBERS: _adjacent(sentence),
        Feature.SPAN_BACK: any(_SPAN.search(p) for p, _ in times),
        Feature.DAY_WORD_WITH_CLOCK: any(
            precision is TimePrecision.MINUTE
            and not _SPAN.search(phrase)
            and not _WRITTEN_DATE.search(phrase)
            for phrase, precision in times
        ),
        Feature.WRITTEN_DATE: any(_WRITTEN_DATE.search(p) for p, _ in times),
        Feature.DATE_ONLY: any(precision is TimePrecision.DAY for _, precision in times),
        Feature.UNRELATED_NUMBER: _has_unrelated_number(sentence),
        Feature.SHARED_DETAIL: _shares_a_detail(sentence),
    }


def feature_holds(sentence: Sentence, feature: Feature) -> bool:
    """Whether ``sentence`` bears out the hand-given label ``feature``."""
    return _checks(sentence)[feature]


def coverage_table(sentences: Iterable[Sentence]) -> dict[Item, dict[Split, int]]:
    """For each item, how many sentences of each set cover it."""
    counts: dict[Item, collections.Counter[Split]] = {item: collections.Counter() for item in Item}
    for sentence in sentences:
        for item in items_of(sentence):
            counts[item][sentence.split] += 1
    return {item: {split: counts[item][split] for split in Split} for item in Item}
