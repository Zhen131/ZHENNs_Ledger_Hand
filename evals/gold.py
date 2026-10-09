"""The test sentences and their gold answers: the shapes, and reading them from a set file.

A set file (``evals/sets/debug.json``, ``evals/sets/final.json``) is a JSON
list of sentences. Every sentence is invented. Each one is an object with:

- ``id``: unique across both sets;
- ``text``: the passage, as a person would type it;
- ``now`` and ``zone``: the current moment (with its offset) and the time
  zone the passage is read in. They are fixed in the sentence, so a gold
  time never depends on when the experiment runs;
- ``language``: ``zh``, ``en`` or ``mixed``;
- ``group``: ``scored``, or ``not_to_record`` for the kinds of passage the
  ledger does not take (futures, a coin paid with another coin, an order
  not filled yet, a plan); those have a ``kind`` and are reported apart;
- ``features``: the hand-given labels of how the sentence is written (see
  ``Feature``); everything that can be read off the gold answer itself is
  not labelled but worked out (``coverage``);
- ``trades``: the gold answer, one object per trade the drafts should hold.

The gold answer states what the drafts of extraction should hold, not what
the finished record would hold: a field the person did not say is empty,
and so is the one of quantity, price and total that the check of a draft
would calculate. A trade object has ``side`` (``buy``, ``sell`` or absent)
and, for each other field the passage says, ``[phrase, value]``:

- ``phrase`` is the piece of the passage the value comes from, exactly as
  it stands there;
- ``value`` is what the draft should hold: a coin or currency as what it
  names (``BTC``, ``USDT``), a number as plain digits, a time as an ISO
  date or moment followed by its precision (``[phrase, moment,
  "minute"]``), a platform or opinion as its text. ``null`` means the
  passage says it but the rules of this program leave the field empty
  (a number or time the core is unsure of).

A field that is absent is not said, and its gold value is empty. ``missing``
lists, by name, what the check of a draft must find missing in the gold
draft: empty when the trade is complete.

Names defined here: ``Split``, ``Language``, ``Group``, ``NotToRecord``,
``Feature``, ``GoldValue``, ``GoldCell``, ``GoldTrade``, ``Sentence``,
``load_set``, ``sentences_from_json``, ``trade_from_json``,
``trade_to_json``, ``gold_draft``, ``SETS_DIR``, ``DEBUG_SET`` and
``FINAL_SET``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft
from ledger_hand.core.validation import Missing
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.reply_table import Field

SETS_DIR = Path(__file__).resolve().parent / "sets"
DEBUG_SET = SETS_DIR / "debug.json"
FINAL_SET = SETS_DIR / "final.json"


class Split(enum.Enum):
    """Which set a sentence belongs to: tuned against, or kept for the final run."""

    DEBUG = "debug"
    FINAL = "final"
    WRITINGS = "writings"


class Language(enum.Enum):
    """The language a sentence is written in."""

    CHINESE = "zh"
    ENGLISH = "en"
    MIXED = "mixed"


class Group(enum.Enum):
    """Whether a sentence counts towards the scores."""

    SCORED = "scored"
    NOT_TO_RECORD = "not_to_record"


class NotToRecord(enum.Enum):
    """The kinds of passage the ledger does not take, reported apart."""

    FUTURES = "futures_or_leverage"
    COIN_FOR_COIN = "coin_for_coin"
    OPEN_ORDER = "open_order"
    PLAN = "plan"


class Feature(enum.Enum):
    """How a sentence is written, where the gold answer alone does not show it."""

    CHINESE_NUMERALS = "chinese_numerals"
    MULTIPLIER = "multiplier"
    THOUSANDS_COMMA = "thousands_comma"
    CURRENCY_WORD = "currency_word"
    PER_PIECE = "per_piece"
    GAP_BEFORE_MULTIPLIER = "gap_before_multiplier"
    SPACE_THOUSANDS = "space_thousands"
    ADJACENT_NUMBERS = "adjacent_numbers"
    SPAN_BACK = "span_back"
    DAY_WORD_WITH_CLOCK = "day_word_with_clock"
    WRITTEN_DATE = "written_date"
    DATE_ONLY = "date_only"
    UNRELATED_NUMBER = "unrelated_number"
    SHARED_DETAIL = "shared_detail"


type GoldValue = Side | str | Decimal | OccurredTime
"""A side, a currency or coin as what it names, a number, a time, or a text."""

_WORD_FIELDS = frozenset({Field.COIN, Field.PRICE_CURRENCY, Field.FEE_CURRENCY})
_NUMBER_FIELDS = frozenset({Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE})
_TEXT_FIELDS = frozenset({Field.PLATFORM, Field.OPINION})
_TRADE_KEYS = frozenset(field.value for field in Field) | {"missing"}
_SENTENCE_KEYS = frozenset(
    {"id", "text", "now", "zone", "language", "group", "kind", "features", "trades"}
)


@dataclass(frozen=True)
class GoldCell:
    """One field of a gold trade: the piece of the passage, and what the draft should hold.

    ``phrase`` is ``None`` when the passage does not say the field; ``value``
    is ``None`` when the draft should leave the field empty.
    """

    phrase: str | None
    value: GoldValue | None


_NOT_SAID = GoldCell(None, None)


@dataclass(frozen=True)
class GoldTrade:
    """What one draft should hold, field by field, and what its check should find missing."""

    cells: Mapping[Field, GoldCell]
    missing: tuple[Missing, ...]

    def cell(self, field: Field) -> GoldCell:
        """The gold cell of ``field``; not said when the trade does not name it."""
        return self.cells.get(field, _NOT_SAID)

    def value(self, field: Field) -> GoldValue | None:
        """What the draft should hold in ``field``."""
        return self.cell(field).value


@dataclass(frozen=True)
class Sentence:
    """One test sentence with its fixed moment, its labels and its gold answer."""

    id: str
    text: str
    now: datetime
    zone: str
    split: Split
    language: Language
    group: Group
    kind: NotToRecord | None
    features: frozenset[Feature]
    trades: tuple[GoldTrade, ...]


def load_set(path: Path, split: Split) -> tuple[Sentence, ...]:
    """The sentences in the set file at ``path``, which holds the ``split`` set."""
    return sentences_from_json(json.loads(path.read_text(encoding="utf-8")), split)


def sentences_from_json(data: object, split: Split) -> tuple[Sentence, ...]:
    """Sentences from the JSON value of a set file; ``ValueError`` on anything malformed."""
    if not isinstance(data, list):
        raise ValueError("a set file holds a list of sentences")
    sentences = tuple(_sentence(item, split) for item in data)
    ids = [sentence.id for sentence in sentences]
    if len(set(ids)) != len(ids):
        raise ValueError("two sentences share an id")
    return sentences


def _sentence(item: object, split: Split) -> Sentence:
    if not isinstance(item, dict) or not set(item) <= _SENTENCE_KEYS:
        raise ValueError(f"not a sentence: {item!r}")
    name = str(item.get("id"))
    try:
        return _parsed_sentence(item, split)
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise ValueError(f"sentence {name}: {error}") from error


def _parsed_sentence(item: Mapping[str, object], split: Split) -> Sentence:
    text = _text(item["text"])
    zone = _text(item["zone"])
    if not is_zone_name(zone):
        raise ValueError(f"not a zone name: {zone!r}")
    now = datetime.fromisoformat(_text(item["now"]))
    if now.utcoffset() is None:
        raise ValueError("the current moment needs an offset")
    group = Group(item["group"])
    kind = NotToRecord(item["kind"]) if "kind" in item else None
    if (group is Group.NOT_TO_RECORD) != (kind is not None):
        raise ValueError("a kind goes with the not_to_record group, and only with it")
    trades = item["trades"]
    if not isinstance(trades, list):
        raise ValueError("trades is a list")
    features = item.get("features", [])
    if not isinstance(features, list):
        raise ValueError("features is a list")
    return Sentence(
        id=_text(item["id"]),
        text=text,
        now=now,
        zone=zone,
        split=split,
        language=Language(item["language"]),
        group=group,
        kind=kind,
        features=frozenset(Feature(name) for name in features),
        trades=tuple(trade_from_json(trade, text, zone) for trade in trades),
    )


def trade_from_json(data: object, text: str, zone: str) -> GoldTrade:
    """A gold trade from its JSON object; every phrase must stand in ``text`` as written."""
    if not isinstance(data, dict) or not set(data) <= _TRADE_KEYS:
        raise ValueError(f"not a trade: {data!r}")
    cells: dict[Field, GoldCell] = {}
    side = data.get(Field.SIDE.value)
    if side is not None:
        cells[Field.SIDE] = GoldCell(None, Side(side))
    for field in Field:
        if field is not Field.SIDE and field.value in data:
            cells[field] = _cell(field, data[field.value], text, zone)
    missing = data.get("missing", [])
    if not isinstance(missing, list):
        raise ValueError("missing is a list")
    return GoldTrade(cells, tuple(Missing[name] for name in missing))


def _cell(field: Field, data: object, text: str, zone: str) -> GoldCell:
    if not isinstance(data, list) or not 2 <= len(data) <= 3:
        raise ValueError(f"{field.value}: a cell is [phrase, value] or [phrase, value, precision]")
    phrase = _text(data[0])
    if not phrase or phrase not in text:
        raise ValueError(f"{field.value}: {phrase!r} is not a piece of the passage")
    raw = data[1]
    if raw is None:
        if len(data) != 2:
            raise ValueError(f"{field.value}: an empty value has no precision")
        return GoldCell(phrase, None)
    if field is Field.TIME:
        if len(data) != 3:
            raise ValueError("time: a time value needs its precision")
        return GoldCell(phrase, _time(_text(raw), TimePrecision(data[2]), zone))
    if len(data) != 2:
        raise ValueError(f"{field.value}: only a time has a precision")
    return GoldCell(phrase, _value(field, _text(raw)))


def _value(field: Field, raw: str) -> GoldValue:
    if field in _NUMBER_FIELDS:
        number = Decimal(raw)
        if not number.is_finite() or raw != raw.strip():
            raise ValueError(f"{field.value}: not a plain number: {raw!r}")
        return number
    if field in _WORD_FIELDS or field in _TEXT_FIELDS:
        if not raw.strip():
            raise ValueError(f"{field.value}: an empty text is written as null")
        return raw
    raise ValueError(f"no value of this kind for {field.value}")


def _time(raw: str, precision: TimePrecision, zone: str) -> OccurredTime:
    if precision is TimePrecision.DAY:
        return OccurredTime(date.fromisoformat(raw), precision, zone)
    moment = datetime.fromisoformat(raw)
    return OccurredTime(moment, precision, zone)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected text, not {value!r}")
    return value


def trade_to_json(trade: GoldTrade) -> dict[str, object]:
    """The JSON object of ``trade``, as a set file writes it."""
    data: dict[str, object] = {}
    for field in Field:
        cell = trade.cell(field)
        if field is Field.SIDE:
            if isinstance(cell.value, Side):
                data[field.value] = cell.value.value
        elif cell.phrase is not None:
            data[field.value] = _cell_to_json(cell)
    data["missing"] = [item.name for item in trade.missing]
    return data


def _cell_to_json(cell: GoldCell) -> list[object]:
    value = cell.value
    if value is None:
        return [cell.phrase, None]
    if isinstance(value, OccurredTime):
        return [cell.phrase, value.value.isoformat(), value.precision.value]
    if isinstance(value, Decimal):
        return [cell.phrase, str(value)]
    return [cell.phrase, str(value)]


def gold_draft(trade: GoldTrade, text: str) -> TradeDraft:
    """The draft the gold answer describes, ready for the check of a draft."""

    def word(field: Field) -> str | None:
        value = trade.value(field)
        return value if isinstance(value, str) else None

    def number(field: Field) -> Decimal | None:
        value = trade.value(field)
        return value if isinstance(value, Decimal) else None

    side = trade.value(Field.SIDE)
    occurred = trade.value(Field.TIME)
    return TradeDraft(
        side=side if isinstance(side, Side) else None,
        coin=word(Field.COIN),
        quantity=number(Field.QUANTITY),
        price=number(Field.PRICE),
        total=number(Field.TOTAL),
        quote=word(Field.PRICE_CURRENCY),
        fee=number(Field.FEE),
        fee_coin=word(Field.FEE_CURRENCY),
        occurred=occurred if isinstance(occurred, OccurredTime) else None,
        platform=word(Field.PLATFORM),
        note=word(Field.OPINION),
        raw_text=text,
    )
