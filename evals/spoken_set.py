"""Sentences said the owner's way, in three tiers, and their gold answers: shapes, reading, checks.

The six recording sets (``evals/sets/spoken-r100-practice.json`` and the
like) hold sentences each said once, in a chat of its own, to the whole
assistant against the exam book (``exam_book``), at the set's fixed moment
and zone. The tiers are the owner's way of speaking as it is (``r100``), a
little tidier (``r80``) and tidy (``r70``). Each tier is cut in two halves:
the odd-numbered sentences are the practice half, which may be looked at
while prompts are tuned; the even-numbered ones are the hidden half, which
only its totals are ever printed of. A file says which half it is
(``half``), so nothing has to be remembered on the command line.

Each sentence has a gold answer, written once before any run:

- ``send``: the trades that should reach the ledger, in the order said,
  each a cell at a time (``GoldTrade``);
- ``ask``: the program should ask about one of the cells named in ``ask``;
- ``cannot_record``: nothing can be recorded, for one of the reasons
  ``why`` names.

A sentence the ledger cannot take yet (a euro payment, a fee for changing
money, a cash balance, a dividend) is not enabled: it says what it waits
for (``wait_for``), and its gold answer is ``cannot_record`` alone, with no
figure.

A cell is written in one of these ways (``GoldCell``):

- ``value`` and ``said``: the cell should be ``value``; ``said`` is the
  piece of what was said that gives it, word for word, or for a time the
  pieces in order;
- ``value``, ``said`` and ``zero``: the fee, said outright to be none;
- ``value`` alone: a cell with no piece of its own (no platform said);
- ``computed``: the program should work it out from the other two amounts;
- ``none``: what was said gives no value (a fee not looked at, no time of
  day); a time may name the ``day`` that was said, with its ``said`` piece;
- ``skip``: not judged (the fee's money when the fee is none at all).

Each trade also names the cells that disagree as said (``suspect``), the
cells whose money should be marked as a guess (``inferred``) and the cells
a question about counts as rightly asked (``ask_ok``; by default every
``none`` and ``suspect`` cell).

``load_spoken_set`` reads a file and checks its shape. ``gold_problems``
checks each gold answer against what was said, the way the program reads
it (every piece tidied first), and gives the problems found, each named by
the sentence's identifier and a few fixed words, never by what was said:
a hidden sentence's words never reach a message.

Names defined here: ``CELLS``, ``AMOUNT_CELLS``, ``SEND``, ``ASK``,
``CANNOT_RECORD``, ``WAITS``, ``HALVES``, ``TIERS``, ``GoldCell``,
``GoldTrade``, ``SpokenGold``, ``SpokenSentence``, ``SpokenSet``,
``load_spoken_set``, ``gold_problems``, ``gold_moment``, ``computed_value``,
``gold_value`` and ``is_hidden``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.core.spoken_text import tidy_spoken
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.core.trade import Amount, TimePrecision
from ledger_hand.core.validation import amounts_agree, third_amount

# The ten cells of a trade that are judged, in the order a trade is told.
CELLS = (
    "side",
    "asset",
    "quantity",
    "price",
    "total",
    "quote",
    "fee",
    "fee_asset",
    "occurred",
    "platform",
)
AMOUNT_CELLS = ("quantity", "price", "total")
_NUMBER_CELLS = frozenset({"quantity", "price", "total", "fee"})
_INFERABLE = frozenset({"quote", "fee_asset"})
SEND = "send"
ASK = "ask"
CANNOT_RECORD = "cannot_record"
_EXPECTS = frozenset({SEND, ASK, CANNOT_RECORD})
# What a sentence not enabled yet waits for in the ledger.
WAITS = frozenset({"eur_payment", "fx_fee", "cash_balance", "dividend"})
HALVES = frozenset({"practice", "hidden"})
TIERS = frozenset({"r100", "r80", "r70"})
# The words that say a fee was none at all, besides a number read as 0.
_ZERO_WORDS = ("没有", "无", "免")
_MINUTE = "%Y-%m-%d %H:%M"
_ID = re.compile(r"^R(100|80|70)-(\d{2})$")


@dataclass(frozen=True)
class GoldCell:
    """One cell of a gold trade; exactly one way of writing it, as the module says."""

    value: str | None = None
    said: tuple[str, ...] = ()
    zero: bool = False
    computed: bool = False
    none: bool = False
    day: str | None = None
    skip: bool = False


@dataclass(frozen=True)
class GoldTrade:
    """One trade of a gold answer: its ten cells and the three lists."""

    cells: Mapping[str, GoldCell]
    suspect: frozenset[str] = frozenset()
    inferred: frozenset[str] = frozenset()
    ask_ok: frozenset[str] = frozenset()

    @property
    def nones(self) -> frozenset[str]:
        """The cells what was said gives no value for."""
        return frozenset(name for name, cell in self.cells.items() if cell.none)

    @property
    def askable(self) -> frozenset[str]:
        """The cells a question about counts as rightly asked."""
        return self.ask_ok or (self.nones | self.suspect)

    @property
    def clean(self) -> bool:
        """Whether this trade could be saved with no cell changed: nothing none, nothing suspect."""
        return not self.nones and not self.suspect


@dataclass(frozen=True)
class SpokenGold:
    expect: str
    trades: tuple[GoldTrade, ...] = ()
    ask: frozenset[str] = frozenset()
    why: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SpokenSentence:
    id: str
    kind: str
    language: str
    enabled: bool
    text: str
    gold: SpokenGold
    wait_for: str | None = None


@dataclass(frozen=True)
class SpokenSet:
    tier: str
    half: str
    book: str
    now: datetime
    zone: str
    sentences: tuple[SpokenSentence, ...]

    @property
    def hidden(self) -> bool:
        return self.half == "hidden"


def is_hidden(path: Path) -> bool:
    """Whether a set file, by its own word, is a hidden half."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("half") == "hidden"


def _cell(data: Mapping[str, object]) -> GoldCell:
    said = data.get("said", ())
    pieces = (said,) if isinstance(said, str) else tuple(str(one) for one in said)  # type: ignore[attr-defined]
    value = data.get("value")
    cell = GoldCell(
        value=None if value is None else str(value),
        said=pieces,
        zero=bool(data.get("zero", False)),
        computed=bool(data.get("computed", False)),
        none=bool(data.get("none", False)),
        day=None if data.get("day") is None else str(data["day"]),
        skip=bool(data.get("skip", False)),
    )
    ways = sum((cell.value is not None, cell.computed, cell.none, cell.skip))
    if ways != 1:
        raise ValueError("a gold cell is written exactly one way")
    if cell.zero and (cell.value != "0" or not cell.said):
        raise ValueError("a fee said to be none is 0, with the words that say so")
    if cell.day is not None and not cell.none:
        raise ValueError("only a time with no time of day names its day")
    return cell


def _names(data: object) -> frozenset[str]:
    names = frozenset(str(one) for one in data or ())  # type: ignore[attr-defined]
    if not names <= set(CELLS):
        raise ValueError("a list of cells names cells of a trade")
    return names


def _trade(data: Mapping[str, object]) -> GoldTrade:
    cells = {name: _cell(data[name]) for name in CELLS}  # type: ignore[arg-type]
    trade = GoldTrade(
        cells=cells,
        suspect=_names(data.get("suspect")),
        inferred=_names(data.get("inferred")),
        ask_ok=_names(data.get("ask_ok")),
    )
    if not trade.inferred <= _INFERABLE:
        raise ValueError("only a trade's money and its fee's money may be guessed")
    side = cells["side"]
    if side.value not in ("buy", "sell") or side.said:
        raise ValueError("a side is buy or sell, with no words of its own")
    return trade


def _gold(data: Mapping[str, object]) -> SpokenGold:
    expect = str(data["expect"])
    if expect not in _EXPECTS:
        raise ValueError(f"unknown gold answer: {expect!r}")
    trades = tuple(_trade(one) for one in data.get("trades", ()))  # type: ignore[attr-defined]
    gold = SpokenGold(
        expect=expect,
        trades=trades,
        ask=_names(data.get("ask")),
        why=frozenset(str(one) for one in data.get("why", ())),  # type: ignore[attr-defined]
    )
    if (expect == CANNOT_RECORD) != bool(gold.why):
        raise ValueError("only an answer that cannot be recorded names its reasons")
    if (expect == ASK) != bool(gold.ask):
        raise ValueError("only an answer that asks names the cells asked")
    if expect == SEND and not trades:
        raise ValueError("an answer that sends names one trade at least")
    return gold


def load_spoken_set(path: Path) -> SpokenSet:
    """The set in ``path``; raises ``ValueError`` when it is not in the shape the module says."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sentences = tuple(
        SpokenSentence(
            id=str(item["id"]),
            kind=str(item["kind"]),
            language=str(item["language"]),
            enabled=bool(item["enabled"]),
            text=str(item["text"]),
            gold=_gold(item["gold"]),
            wait_for=None if item.get("wait_for") is None else str(item["wait_for"]),
        )
        for item in data["sentences"]
    )
    spoken = SpokenSet(
        tier=str(data["tier"]),
        half=str(data["half"]),
        book=str(data["book"]),
        now=datetime.fromisoformat(data["now"]),
        zone=str(data["zone"]),
        sentences=sentences,
    )
    if spoken.tier not in TIERS or spoken.half not in HALVES or spoken.book != "exam":
        raise ValueError("a set names its tier, its half and the exam book")
    if spoken.now.utcoffset() is None:
        raise ValueError("the set's moment carries an offset")
    ids = [sentence.id for sentence in sentences]
    if len(set(ids)) != len(ids):
        raise ValueError("every sentence has an identifier of its own")
    for sentence in sentences:
        if sentence.enabled != (sentence.wait_for is None):
            raise ValueError("a sentence not enabled, and only it, says what it waits for")
        if sentence.wait_for is not None and sentence.wait_for not in WAITS:
            raise ValueError(f"a sentence waits for one of {sorted(WAITS)}")
        if not sentence.enabled and (sentence.gold.expect != CANNOT_RECORD or sentence.gold.trades):
            raise ValueError("a sentence not enabled has only 'cannot be recorded' as its gold")
    return spoken


def gold_moment(text: str, zone: str) -> datetime:
    """A gold time, written to the minute in local time, as a moment in ``zone``."""
    return datetime.strptime(text, _MINUTE).replace(tzinfo=ZoneInfo(zone))


# --- the checks against what was said -------------------------------------------------


def gold_problems(spoken: SpokenSet) -> list[tuple[str, str]]:
    """Every problem of the set's gold answers: (the sentence's identifier, fixed words)."""
    found: list[tuple[str, str]] = []
    for sentence in spoken.sentences:
        found.extend((sentence.id, words) for words in _sentence_problems(sentence, spoken))
    return found


def _sentence_problems(sentence: SpokenSentence, spoken: SpokenSet) -> list[str]:
    problems: list[str] = []
    matched = _ID.match(sentence.id)
    if matched is None or f"r{matched.group(1)}" != spoken.tier:
        problems.append("the identifier is not of this tier")
    elif (int(matched.group(2)) % 2 == 1) != (spoken.half == "practice"):
        problems.append("odd identifiers are practice, even ones hidden")
    for number, trade in enumerate(sentence.gold.trades, start=1):
        problems.extend(
            f"trade {number}: {words}" for words in _trade_problems(trade, sentence, spoken)
        )
    return problems


def _trade_problems(trade: GoldTrade, sentence: SpokenSentence, spoken: SpokenSet) -> list[str]:
    problems: list[str] = []
    for name, cell in trade.cells.items():
        for piece in cell.said:
            if piece not in sentence.text:
                problems.append(f"{name}: a piece is not in what was said")
        problems.extend(f"{name}: {words}" for words in _cell_problems(name, cell, spoken))
    amounts = _amounts(trade)
    if len(amounts) == 3:
        agree = amounts_agree(amounts["quantity"], amounts["price"], amounts["total"])
        if trade.suspect and agree:
            problems.append("the cells marked to disagree agree")
        if not trade.suspect and not agree:
            problems.append("the three amounts disagree, and no cell is marked")
    for name in AMOUNT_CELLS:
        if trade.cells[name].computed and computed_value(trade, name) is None:
            problems.append(f"{name}: cannot be worked out from the other two")
    return problems


def _cell_problems(name: str, cell: GoldCell, spoken: SpokenSet) -> list[str]:
    if cell.skip or cell.computed:
        return []
    if cell.none:
        if cell.day is None:
            return []
        return _day_problems(cell, spoken)
    if name == "occurred":
        return _time_problems(cell, spoken)
    if name in _NUMBER_CELLS and cell.said:
        return _number_problems(cell, spoken)
    if name in _NUMBER_CELLS and not cell.said:
        return ["a number is given with the words that give it"]
    return []


def _tidied(piece: str, zone: str) -> str:
    return tidy_spoken(piece, zone).text


def _number_problems(cell: GoldCell, spoken: SpokenSet) -> list[str]:
    (piece,) = cell.said
    tidied = _tidied(piece, spoken.zone)
    reading = read_number(tidied)
    read = reading.value if isinstance(reading, Recognised) else None
    assert cell.value is not None
    if cell.zero:
        if read == 0 or any(word in tidied for word in _ZERO_WORDS):
            return []
        return ["the words do not say the fee is none"]
    if read is None or read != Decimal(cell.value):
        return ["the words do not read as the value"]
    return []


def _read_moment(cell: GoldCell, spoken: SpokenSet) -> TimeRecognised | None:
    joined = _tidied("".join(cell.said), spoken.zone)
    reading = read_time(joined, spoken.now, spoken.zone)
    return reading if isinstance(reading, TimeRecognised) else None


def _time_problems(cell: GoldCell, spoken: SpokenSet) -> list[str]:
    if not cell.said:
        return ["a time is given with the words that give it"]
    reading = _read_moment(cell, spoken)
    if reading is None or not isinstance(reading.time.value, datetime):
        return ["the words do not read as a moment"]
    assert cell.value is not None
    read = reading.time.value.astimezone(ZoneInfo(spoken.zone)).strftime(_MINUTE)
    return [] if read == cell.value else ["the words do not read as the value"]


def _day_problems(cell: GoldCell, spoken: SpokenSet) -> list[str]:
    reading = _read_moment(cell, spoken)
    if reading is None or reading.time.precision is not TimePrecision.DAY:
        return ["the words do not read as a day alone"]
    return [] if str(reading.time.value) == cell.day else ["the words do not read as the day"]


def _amounts(trade: GoldTrade) -> dict[str, Decimal]:
    found: dict[str, Decimal] = {}
    for name in AMOUNT_CELLS:
        value = trade.cells[name].value
        if value is None:
            continue
        try:
            found[name] = Decimal(value)
        except InvalidOperation:
            continue
    return found


def computed_value(trade: GoldTrade, name: str) -> Decimal | None:
    """The amount ``name`` worked out from the other two gold amounts, as the program would."""
    amounts = _amounts(trade)
    others = {Amount(other): amounts[other] for other in AMOUNT_CELLS if other != name}
    if len(others) != 2:
        return None
    return third_amount(Amount(name), others)


def gold_value(trade: GoldTrade, name: str) -> str | None:
    """The value a sent trade should hold in ``name``; ``None`` for a cell with no value."""
    cell = trade.cells[name]
    if cell.computed:
        worked = computed_value(trade, name)
        return None if worked is None else str(worked)
    return cell.value
