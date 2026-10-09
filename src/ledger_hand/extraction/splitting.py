"""Split first, then extract: a passage cut into one segment per trade, each extracted on its own.

This is the other way to read a passage that reports several trades. The
way the product uses is ``extract`` alone: the whole passage in one call,
one list of rows back. ``split_then_extract`` takes what ``extract`` takes,
and a version of the prompt that splits (``prompts/split.py``), and gives
back a ``SplitExtraction``:

- ``extraction``: what the passage gave, in the shapes ``extract`` gives
  (``Extracted``, ``PassageRefused``, ``ReplyUnreadable``, ``ModelFailed``),
  so that whatever reads the one reads the other. Its calls are every call
  made for the passage, the split's included, in order;
- ``route``: whether the passage went segment by segment or whole, and why
  (``Route``);
- ``trades_listed``: how many trades the split listed, or ``None`` when its
  reply could not be read or the model failed on it;
- ``segments``: the segments the split gave, when it listed two trades or
  more and every piece was found; none otherwise;
- ``steps``: for every call made, in order, what it was for (``CallStep``);
- ``draft_calls``: the calls whose replies the drafts are made from, in
  order.

The way:

1. The passage is checked as ``extract`` checks it; a passage it refuses is
   not sent at all.
2. The model is asked for the pieces of the passage each trade needs
   (``split_table``). A reply that misses the table's shape is asked about
   again, as often as extraction asks again.
3. A split that lists fewer than two trades leaves nothing to cut: the
   whole passage goes through ``extract`` once, exactly as without splitting
   (``Route.WHOLE``). Otherwise the pieces become segments (``segments``):
   only the passage's own text, one segment per trade; fewer than two
   segments (a trade with no piece gives none) go the same way.
4. A split that went wrong sends the whole passage the same way, and the
   route says why: its reply could not be read, the model failed on it, or
   a piece is not a piece of the passage (``Route.fell_back``).
5. Two segments or more: each goes through ``extract`` on its own, with the
   caller's extraction prompt, parameters and asking again. A segment whose
   extraction fails (a reply that could not be read after asking again, or
   a model failure) makes the passage fail the same way, and the segments
   after it are not sent.
6. The rows the model wrote for all the segments, in order, are read once
   more against the whole passage by extraction's own program side:
   ``extract`` is handed them as the reply of a stand-in model that answers
   with that table and nothing else (``_MergedTable``). So the drafts and
   the issues are exactly what extraction makes of those rows for the whole
   passage: every phrase is checked against the whole passage (one that
   runs across the comma between two runs of a segment is not a piece
   of it, and is left empty with an issue that says so); every draft's
   original text is the whole passage; the positions in the issues count
   among all the drafts; the numbers no trade used are those of the whole
   passage; and a row that two segments both gave is marked as given twice.
   Should the rows of all the segments be more than one reply may hold, the
   whole passage goes the one-list way after all (``Route.MERGED_TOO_LONG``).

It never raises for anything in the passage or in a reply; it raises only
for a mistake of the calling code, as ``extract`` does.

Names defined here: ``split_then_extract``, ``SplitExtraction``, ``Route``,
``Purpose`` and ``CallStep``.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.trade import Side
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.extractor import (
    DEFAULT_ASKS_AGAIN,
    MAX_ASKS_AGAIN,
    Extracted,
    Extraction,
    PassageRefused,
    extract,
)
from ledger_hand.extraction.passage import Passage, PieceMiss
from ledger_hand.extraction.passage_check import passage_problem
from ledger_hand.extraction.prompting import PROBLEM_MARK, PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.split import SPLIT_PROMPT
from ledger_hand.extraction.reply_parser import ReplyRow, ReplyRows, read_reply
from ledger_hand.extraction.reply_table import SIDE_WORDS, TRADES_KEY, Field
from ledger_hand.extraction.segments import PieceMissed, segments_of
from ledger_hand.extraction.split_table import (
    SPLIT_TABLE,
    SplitProblem,
    SplitPromptVersion,
    SplitUnreadable,
    example_split_reply,
    read_split_reply,
)
from ledger_hand.ports import (
    FinishReason,
    JsonSchema,
    Message,
    ModelError,
    ModelParameters,
    ModelPort,
    ModelReply,
    ReplyRecord,
    Role,
)


class Route(enum.Enum):
    """How the passage was read; the value says it in words."""

    SEGMENTS = "split into segments, each extracted on its own"
    WHOLE = "fewer than two trades or segments: the whole passage extracted once"
    SPLIT_UNREADABLE = "the reply to the split could not be read: the whole passage extracted once"
    SPLIT_FAILED = "the model failed on the split: the whole passage extracted once"
    PIECE_NOT_IN_PASSAGE = "a piece is not a piece of the passage: the whole passage extracted once"
    PIECE_CUTS_A_NUMBER = (
        "a piece is in the passage only as part of a longer number: "
        "the whole passage extracted once"
    )
    MERGED_TOO_LONG = (
        "the rows of all segments are more than one reply may hold: "
        "the whole passage extracted once"
    )
    REFUSED = "the passage was not sent"

    @property
    def fell_back(self) -> bool:
        """Whether the split went wrong, so that the whole passage was extracted instead."""
        return self not in (Route.SEGMENTS, Route.WHOLE, Route.REFUSED)


class Purpose(enum.Enum):
    """What a call was made for."""

    SPLIT = "split"
    EXTRACT = "extract"


@dataclass(frozen=True)
class CallStep:
    """What one call was for: the split, or extraction of a segment or of the whole passage.

    ``segment`` counts from 0; it is ``None`` for the split and for the
    whole passage.
    """

    purpose: Purpose
    segment: int | None


@dataclass(frozen=True)
class SplitExtraction:
    """What the passage gave, how it was read, and what each call was for."""

    extraction: Extraction
    route: Route
    trades_listed: int | None
    segments: tuple[str, ...]
    steps: tuple[CallStep, ...]
    draft_calls: tuple[int, ...]


@dataclass(frozen=True)
class _Reading:
    """What every extraction of one passage is handed."""

    model: ModelPort
    now: datetime
    zone: str
    coins: CoinTable
    prompt: PromptVersion
    parameters: ModelParameters | None
    asks_again: int

    def extract(self, text: str, model: ModelPort | None = None) -> Extraction:
        return extract(
            text,
            self.model if model is None else model,
            now=self.now,
            zone=self.zone,
            coins=self.coins,
            prompt=self.prompt,
            parameters=self.parameters,
            asks_again=self.asks_again,
        )


@dataclass
class _Made:
    """The calls made so far for one passage, what each was for, and the trades the split listed."""

    listed: int | None
    calls: list[ReplyRecord] = dataclasses.field(default_factory=list)
    steps: list[CallStep] = dataclasses.field(default_factory=list)

    def add(self, records: Sequence[ReplyRecord], step: CallStep) -> None:
        self.calls.extend(records)
        self.steps.extend(step for _ in records)


def split_then_extract(
    passage: str,
    model: ModelPort,
    *,
    now: datetime,
    zone: str,
    coins: CoinTable = BUILT_IN_TABLE,
    prompt: PromptVersion = FIRST_PROMPT,
    split_prompt: SplitPromptVersion = SPLIT_PROMPT,
    parameters: ModelParameters | None = None,
    asks_again: int = DEFAULT_ASKS_AGAIN,
) -> SplitExtraction:
    """The drafts in ``passage``, read one segment per trade when the split gives several.

    The arguments are ``extract``'s, and ``split_prompt`` the version of the
    prompt that splits; ``asks_again`` holds for the split as for extraction.
    """
    _check_arguments(passage, now, zone, asks_again)
    problem = passage_problem(passage)
    if problem is not None:
        return SplitExtraction(PassageRefused(problem), Route.REFUSED, None, (), (), ())
    reading = _Reading(model, now, zone, coins, prompt, parameters, asks_again)
    made = _Made(listed=None)
    split = _split(passage, reading, split_prompt, made)
    if isinstance(split, Route):
        return _whole(passage, reading, split, (), made)
    made.listed = len(split)
    if len(split) < 2:
        return _whole(passage, reading, Route.WHOLE, (), made)
    segments = segments_of(Passage(passage), split)
    if isinstance(segments, PieceMissed):
        return _whole(passage, reading, _MISSED[segments.miss], (), made)
    if len(segments) < 2:
        return _whole(passage, reading, Route.WHOLE, segments, made)
    return _by_segments(passage, reading, segments, made)


_MISSED = {
    PieceMiss.NOT_IN_PASSAGE: Route.PIECE_NOT_IN_PASSAGE,
    PieceMiss.CUTS_A_NUMBER: Route.PIECE_CUTS_A_NUMBER,
}


def _check_arguments(passage: object, now: object, zone: object, asks_again: object) -> None:
    if not isinstance(passage, str):
        raise TypeError(f"the passage is text, not {type(passage).__name__}")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    if not is_zone_name(zone):
        raise ValueError(f"not a time zone name: {zone!r}")
    if isinstance(asks_again, bool) or not isinstance(asks_again, int):
        raise TypeError(f"asks_again is a whole number, not {type(asks_again).__name__}")
    if not 0 <= asks_again <= MAX_ASKS_AGAIN:
        raise ValueError(f"asks_again must be from 0 to {MAX_ASKS_AGAIN}")


def _split(
    passage: str, reading: _Reading, prompt: SplitPromptVersion, made: _Made
) -> tuple[tuple[str, ...], ...] | Route:
    """The pieces of each trade as the model copied them, or why the whole passage goes on."""
    problems: list[SplitProblem] = []
    for _ in range(reading.asks_again + 1):
        last = problems[-1] if problems else None
        try:
            reply = reading.model.chat(
                _messages(prompt, passage, last),
                reply_schema=SPLIT_TABLE,
                parameters=reading.parameters,
            )
        except ModelError:
            return Route.SPLIT_FAILED
        made.add((reply.record,), CallStep(Purpose.SPLIT, None))
        read = read_split_reply(reply)
        if not isinstance(read, SplitUnreadable):
            return read
        problems.append(read.problem)
    return Route.SPLIT_UNREADABLE


def _messages(
    prompt: SplitPromptVersion, passage: str, problem: SplitProblem | None
) -> tuple[Message, ...]:
    messages = [Message(Role.SYSTEM, prompt.instructions)]
    for example in prompt.examples:
        messages.append(Message(Role.USER, example.passage))
        messages.append(Message(Role.ASSISTANT, example_split_reply(example)))
    messages.append(Message(Role.USER, passage))
    if problem is not None:
        messages.append(Message(Role.USER, prompt.ask_again.replace(PROBLEM_MARK, problem.value)))
    return tuple(messages)


def _whole(
    passage: str, reading: _Reading, route: Route, segments: tuple[str, ...], made: _Made
) -> SplitExtraction:
    """The whole passage extracted once, as without splitting, after the calls made so far."""
    result = reading.extract(passage)
    records = () if isinstance(result, PassageRefused) else result.calls
    made.add(records, CallStep(Purpose.EXTRACT, None))
    drafts_from = (len(made.calls) - 1,) if isinstance(result, Extracted) else ()
    extraction = _with_calls(result, made.calls)
    return SplitExtraction(extraction, route, made.listed, segments, tuple(made.steps), drafts_from)


def _by_segments(
    passage: str, reading: _Reading, segments: tuple[str, ...], made: _Made
) -> SplitExtraction:
    """Each segment extracted on its own; the rows of all of them read against the whole passage."""
    rows: list[ReplyRow] = []
    drafts_from: list[int] = []
    for number, segment in enumerate(segments):
        keeping = _Keeping(reading.model)
        result = reading.extract(segment, keeping)
        records = () if isinstance(result, PassageRefused) else result.calls
        made.add(records, CallStep(Purpose.EXTRACT, number))
        if not isinstance(result, Extracted):
            failed = _with_calls(result, made.calls)
            steps = tuple(made.steps)
            return SplitExtraction(failed, Route.SEGMENTS, made.listed, segments, steps, ())
        drafts_from.append(len(made.calls) - 1)
        rows.extend(_rows_of(keeping.replies[-1]))
    merged = reading.extract(passage, _MergedTable(rows))
    if not isinstance(merged, Extracted):
        return _whole(passage, reading, Route.MERGED_TOO_LONG, segments, made)
    extracted = Extracted(merged.drafts, merged.issues, tuple(made.calls))
    steps = tuple(made.steps)
    return SplitExtraction(
        extracted, Route.SEGMENTS, made.listed, segments, steps, tuple(drafts_from)
    )


def _rows_of(reply: ModelReply) -> tuple[ReplyRow, ...]:
    """The rows of the reply extraction made its drafts from, which it read as the table."""
    read = read_reply(reply)
    if not isinstance(read, ReplyRows):
        raise AssertionError("extraction gave drafts from a reply that is not the table")
    return read.rows


def _with_calls(result: Extraction, calls: Sequence[ReplyRecord]) -> Extraction:
    """``result`` holding ``calls``, every call made for the passage, instead of its own."""
    if isinstance(result, PassageRefused):
        return result
    return dataclasses.replace(result, calls=tuple(calls))


class _Keeping:
    """A model port that passes every call on and keeps the replies."""

    def __init__(self, inner: ModelPort) -> None:
        self._inner = inner
        self.replies: list[ModelReply] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        reply = self._inner.chat(messages, reply_schema=reply_schema, parameters=parameters)
        self.replies.append(reply)
        return reply


_SIDE_WORD: dict[Side | None, str] = {side: word for word, side in SIDE_WORDS.items()}


class _MergedTable:
    """A stand-in model that answers every call with one table: the rows of all the segments.

    It is handed to ``extract`` only, so that extraction reads those rows
    against the whole passage; it is never asked anything else, and its
    record of the call is not kept.
    """

    def __init__(self, rows: Sequence[ReplyRow]) -> None:
        written = [
            {Field.SIDE.value: _SIDE_WORD[row.side], **{f.value: t for f, t in row.cells.items()}}
            for row in rows
        ]
        self._text = json.dumps({TRADES_KEY: written}, ensure_ascii=False)

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        record = ReplyRecord(
            model="",
            elapsed_seconds=0.0,
            prompt_tokens=None,
            reply_tokens=None,
            finish=FinishReason.STOPPED,
        )
        return ModelReply(text=self._text, record=record)
