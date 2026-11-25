"""The questions about the ledger, their gold answers, and how one answer is judged.

The set, ``evals/sets/asks.json``, holds groups of sentences said in one
chat each (most groups hold one sentence; a question asked on from the one
before makes a group of two), the fixed moment and zone they are read at,
and for each sentence its gold answers: one for each tool taken as right.
A gold answer names the tool and, for the two narrowed tools, the first and
last day (``null`` for all time), the asset (``null`` for all assets) and,
for ``list_trades`` only, the side (``null`` for both). Two more kinds of
gold answer stand for what is right without a table: ``no_tool`` (the
assistant cannot answer, and calls nothing) and ``no_such_asset`` (the
program says the ledger has no such asset, naming ``word``).

``judge_answer`` compares the last lookup of the turn with the gold answers
and gives one of these (``Verdict``):

- ``RIGHT``: the tool is one of the gold answers, and the days, the asset
  and the side are exactly its own; or, for ``no_tool``, no table was given;
  or, for ``no_such_asset``, the program said so with the word;
- ``WIDER``: the tool is right, and each condition is the gold one or
  wider (all time, all assets, both sides, or days that hold the gold days),
  at least one wider: the program dropped something, or the model left the
  period out;
- ``OFF``: a table was given whose conditions are narrower than the gold
  or different from it (other days, an asset or a side the user did not
  ask for), whose tool is not a gold one, or that answers a question that
  has no table;
- ``NO_TABLE``: a question that has a table got none: the program could not
  read the period, said there was no such asset, or the model answered
  without a tool.

Only ``RIGHT`` counts as looked up right. The pass lines (``passes``): no
sentence is ``OFF``; the six sentences Q1 to Q6 are all ``RIGHT``; at least
``RIGHT_SHARE`` of all sentences are ``RIGHT``.

Names defined here: ``ASK_SET``, ``RIGHT_SHARE``, ``FIRST_SIX``, ``Gold``,
``AskSentence``, ``AskGroup``, ``AskSet``, ``load_ask_set``, ``Found``,
``Verdict``, ``judge_answer``, ``passes``, ``totals``, ``markdown``, ``BOOKS``,
``HALVES`` and ``check_book_and_half``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ledger_hand.assistant.tools import ToolName

ASK_SET = Path(__file__).resolve().parent / "sets" / "asks.json"
# The same share as the whole-trade pass line of the extraction set.
RIGHT_SHARE = Decimal("0.8")
FIRST_SIX = ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")
# What a set may name as its book and its half; ``None`` names neither.
BOOKS = frozenset({None, "exam"})
HALVES = frozenset({None, "practice", "hidden"})
NO_TOOL = "no_tool"
NO_SUCH_ASSET = "no_such_asset"
_NARROWED = frozenset({ToolName.LIST_TRADES.value, ToolName.GET_PERIOD_SUMMARY.value})
_TOOLS = frozenset(
    {
        ToolName.LIST_TRADES.value,
        ToolName.GET_PERIOD_SUMMARY.value,
        ToolName.GET_POSITIONS.value,
        ToolName.LIST_ASSETS.value,
    }
)


@dataclass(frozen=True)
class Gold:
    """One gold answer: the tool, and for a narrowed tool its days, asset and side."""

    tool: str
    first_day: date | None = None
    last_day: date | None = None
    asset: str | None = None
    side: str | None = None
    word: str | None = None


@dataclass(frozen=True)
class AskSentence:
    """One sentence and its gold answers."""

    id: str
    text: str
    gold: tuple[Gold, ...]


@dataclass(frozen=True)
class AskGroup:
    """Sentences said one after the other in one chat."""

    sentences: tuple[AskSentence, ...]


@dataclass(frozen=True)
class AskSet:
    """The groups, and the moment and zone every sentence is read at.

    ``book`` is the book the ledger holds (``exam`` for the exam book,
    ``None`` for the fake ledger's invented book); ``half`` is ``hidden``
    for a hidden half, whose sentences are never printed, ``practice`` for
    the other half, ``None`` for a set not cut in two.
    """

    now: datetime
    zone: str
    groups: tuple[AskGroup, ...]
    book: str | None = None
    half: str | None = None

    @property
    def sentences(self) -> tuple[AskSentence, ...]:
        return tuple(sentence for group in self.groups for sentence in group.sentences)


def _day(value: object) -> date | None:
    return None if value is None else date.fromisoformat(str(value))


def _gold(entry: Mapping[str, object], where: str) -> Gold:
    tool = str(entry["tool"])
    if tool not in {*_TOOLS, NO_TOOL, NO_SUCH_ASSET}:
        raise ValueError(f"{where}: {tool!r} is not a read tool, {NO_TOOL} or {NO_SUCH_ASSET}")
    gold = Gold(
        tool=tool,
        first_day=_day(entry.get("from")),
        last_day=_day(entry.get("to")),
        asset=entry.get("asset") and str(entry["asset"]),
        side=entry.get("side") and str(entry["side"]),
        word=entry.get("word") and str(entry["word"]),
    )
    if (gold.first_day is None) != (gold.last_day is None):
        raise ValueError(f"{where}: a gold answer has both days or neither")
    if gold.side is not None and tool != ToolName.LIST_TRADES.value:
        raise ValueError(f"{where}: only list_trades has a side")
    if (tool == NO_SUCH_ASSET) != (gold.word is not None):
        raise ValueError(f"{where}: {NO_SUCH_ASSET}, and only it, names a word")
    return gold


def check_book_and_half(book: object, half: object) -> None:
    """Raises ``ValueError`` unless ``book`` and ``half`` are ones a set may name, or none."""
    if book not in BOOKS:
        raise ValueError(f"a set's book is one of {sorted(map(str, BOOKS - {None}))}, or none")
    if half not in HALVES:
        raise ValueError(f"a set's half is one of {sorted(map(str, HALVES - {None}))}, or none")


def load_ask_set(path: Path = ASK_SET) -> AskSet:
    """The set in ``path``; ``ValueError`` when it is not in the expected shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(data["now"])
    if now.utcoffset() is None:
        raise ValueError("the set's moment must carry an offset")
    groups = tuple(
        AskGroup(
            sentences=tuple(
                AskSentence(
                    id=entry["id"],
                    text=entry["text"],
                    gold=tuple(_gold(gold, entry["id"]) for gold in entry["gold"]),
                )
                for entry in group
            )
        )
        for group in data["groups"]
    )
    ask_set = AskSet(
        now=now, zone=data["zone"], groups=groups, book=data.get("book"), half=data.get("half")
    )
    check_book_and_half(ask_set.book, ask_set.half)
    ids = [sentence.id for sentence in ask_set.sentences]
    if len(set(ids)) != len(ids):
        raise ValueError("two sentences share an identifier")
    if any(not sentence.gold for sentence in ask_set.sentences):
        raise ValueError("every sentence has a gold answer")
    return ask_set


@dataclass(frozen=True)
class Found:
    """What one sentence came to: the last lookup's tool and conditions, if a table was given,
    and the program's own words, if it answered itself."""

    tool: str | None = None
    first_day: date | None = None
    last_day: date | None = None
    asset: str | None = None
    side: str | None = None
    program_words: str | None = None


class Verdict(enum.Enum):
    """How one answer compares with the gold answers."""

    RIGHT = "right"
    WIDER = "wider"
    OFF = "narrower or off"
    NO_TABLE = "no table"


class _Fit(enum.Enum):
    SAME = "same"
    WIDER = "wider"
    OFF = "off"


def _fit_days(found: Found, gold: Gold) -> _Fit:
    if (found.first_day, found.last_day) == (gold.first_day, gold.last_day):
        return _Fit.SAME
    if found.first_day is None or found.last_day is None:
        return _Fit.WIDER
    if gold.first_day is None or gold.last_day is None:
        return _Fit.OFF
    holds = found.first_day <= gold.first_day and found.last_day >= gold.last_day
    return _Fit.WIDER if holds else _Fit.OFF


def _fit_value(found: str | None, gold: str | None) -> _Fit:
    if found == gold:
        return _Fit.SAME
    return _Fit.WIDER if found is None else _Fit.OFF


def _compared(found: Found, gold: Gold) -> Verdict:
    if gold.tool not in _NARROWED:
        return Verdict.RIGHT
    fits = [_fit_days(found, gold), _fit_value(found.asset, gold.asset)]
    if gold.tool == ToolName.LIST_TRADES.value:
        fits.append(_fit_value(found.side, gold.side))
    if _Fit.OFF in fits:
        return Verdict.OFF
    return Verdict.WIDER if _Fit.WIDER in fits else Verdict.RIGHT


def judge_answer(sentence: AskSentence, found: Found) -> Verdict:
    """How ``found`` compares with the gold answers of ``sentence``."""
    kinds = {gold.tool for gold in sentence.gold}
    if found.tool is None:
        if NO_TOOL in kinds:
            return Verdict.RIGHT
        words = (found.program_words or "").casefold()
        said_no_asset = "has no asset called" in words
        if any(
            gold.tool == NO_SUCH_ASSET and gold.word and gold.word.casefold() in words
            for gold in sentence.gold
        ):
            return Verdict.RIGHT if said_no_asset else Verdict.NO_TABLE
        return Verdict.NO_TABLE
    matching = [gold for gold in sentence.gold if gold.tool == found.tool]
    if not matching:
        asked = [gold for gold in sentence.gold if gold.tool == NO_SUCH_ASSET]
        if asked and found.asset is None:
            return Verdict.WIDER
        return Verdict.OFF
    verdicts = [_compared(found, gold) for gold in matching]
    for verdict in (Verdict.RIGHT, Verdict.WIDER):
        if verdict in verdicts:
            return verdict
    return Verdict.OFF


def passes(verdicts: Mapping[str, Verdict], first: Sequence[str] = FIRST_SIX) -> dict[str, bool]:
    """The three pass lines, each passed or not.

    ``first`` are the sentences that must all be right; with none (the
    exam's sets, which hold no Q1 to Q6), that line is left out.
    """
    right = sum(verdict is Verdict.RIGHT for verdict in verdicts.values())
    lines = {
        "nothing narrower or off": Verdict.OFF not in verdicts.values(),
        "Q1 to Q6 all right": all(verdicts.get(key) is Verdict.RIGHT for key in first),
        "at least 80% right": Decimal(right) >= RIGHT_SHARE * len(verdicts),
    }
    if not first:
        del lines["Q1 to Q6 all right"]
    return lines


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _found_words(found: Found) -> str:
    if found.tool is None:
        return f"no table: {found.program_words}" if found.program_words else "no table"
    days = (
        f"{found.first_day.isoformat()} to {found.last_day.isoformat()}"
        if found.first_day and found.last_day
        else "all time"
    )
    side = f", {found.side}" if found.side else ""
    return f"`{found.tool}` {days}, {found.asset or 'all assets'}{side}"


def _gold_words(gold: Gold) -> str:
    if gold.tool == NO_SUCH_ASSET:
        return f"no such asset: {gold.word}"
    return (
        _found_words(
            Found(
                tool=gold.tool,
                first_day=gold.first_day,
                last_day=gold.last_day,
                asset=gold.asset,
                side=gold.side,
            )
        )
        if gold.tool != NO_TOOL
        else NO_TOOL
    )


def totals(verdicts: Mapping[str, Verdict]) -> dict[str, int]:
    """How many sentences came out each way, by the verdict's name."""
    return {verdict.name: sum(one is verdict for one in verdicts.values()) for verdict in Verdict}


def markdown(
    rows: Sequence[tuple[AskSentence, Found, Verdict, str]],
    conditions: Mapping[str, object],
    first: Sequence[str] = FIRST_SIX,
) -> str:
    """The table of a run, one row a sentence, the count, and the three pass lines."""
    verdicts = {sentence.id: verdict for sentence, _, verdict, _ in rows}
    right = sum(verdict is Verdict.RIGHT for verdict in verdicts.values())
    lines = [
        f"Model `{conditions['model']}`, prompt `{conditions['prompt']}`: "
        f"looked up right on {right} of {len(rows)} sentences.",
        "",
        *(
            f"- {name}: {'passed' if passed else 'NOT passed'}"
            for name, passed in passes(verdicts, first).items()
        ),
        "",
        "| Sentence | Gold | Table given | Verdict | Words by |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sentence, found, verdict, words_by in rows:
        gold = "; ".join(_gold_words(gold) for gold in sentence.gold)
        lines.append(
            f"| {sentence.id} | {_cell(gold)} | {_cell(_found_words(found))} "
            f"| {verdict.value} | {_cell(words_by)} |"
        )
    return "\n".join(lines) + "\n"
