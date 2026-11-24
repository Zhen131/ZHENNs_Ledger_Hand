"""The assistant's set of sentences, and the measure of the model's first step on each.

The set, ``evals/sets/tools.json``, holds sentences with the first steps
taken as right for each (``accept``: tool names, or ``no_tool`` for an
answer without a tool), the words a copied argument of the first step should
hold (``copied``), and the fixed moment and zone every sentence is read at.

``score_first_step`` judges one first step. Only the tools' names count:
with no call, the step is right when ``no_tool`` is accepted; with calls,
when every one of them is accepted. Whether the arguments follow the rules
does not count toward it. Beside it two things are noted that are not part
of the pass line: which expected words a copied argument holds, and what
the program's judging (``assistant.judging``) says of each call, so that a
copy the program would refuse ("BTC" for "比特币", "2026-10-06" for
"10月6号") is listed sentence by sentence.

Names defined here: ``TOOL_SET``, ``NO_TOOL``, ``ToolSentence``, ``ToolSet``,
``load_tool_set``, ``FirstStep``, ``score_first_step`` and ``markdown``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ledger_hand.assistant.judging import Misstep, judge
from ledger_hand.assistant.tools import ToolName
from ledger_hand.ports import ToolCall

TOOL_SET = Path(__file__).resolve().parent / "sets" / "tools.json"
NO_TOOL = "no_tool"
_ANSWERS = frozenset({NO_TOOL, *(name.value for name in ToolName)})


@dataclass(frozen=True)
class ToolSentence:
    """One sentence, the first steps taken as right, and the words a copy should hold."""

    id: str
    text: str
    accept: frozenset[str]
    copied: tuple[str, ...]


@dataclass(frozen=True)
class ToolSet:
    """The sentences, and the moment and zone they are all read at."""

    now: datetime
    zone: str
    sentences: tuple[ToolSentence, ...]


def load_tool_set(path: Path = TOOL_SET) -> ToolSet:
    """The set in ``path``; ``ValueError`` when it is not in the expected shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(data["now"])
    if now.utcoffset() is None:
        raise ValueError("the set's moment must carry an offset")
    sentences = tuple(
        ToolSentence(
            id=entry["id"],
            text=entry["text"],
            accept=frozenset(entry["accept"]),
            copied=tuple(entry["copied"]),
        )
        for entry in data["sentences"]
    )
    for sentence in sentences:
        if not sentence.accept or not sentence.accept <= _ANSWERS:
            raise ValueError(f"{sentence.id}: an accepted step is not a tool or {NO_TOOL}")
    if len({sentence.id for sentence in sentences}) != len(sentences):
        raise ValueError("two sentences share an identifier")
    return ToolSet(now=now, zone=data["zone"], sentences=sentences)


@dataclass(frozen=True)
class FirstStep:
    """How the first step went on one sentence."""

    sentence: ToolSentence
    calls: tuple[ToolCall, ...]
    text: str
    right: bool
    words_found: tuple[str, ...]
    words_missing: tuple[str, ...]
    refused: tuple[str, ...]


def score_first_step(sentence: ToolSentence, calls: Sequence[ToolCall], text: str) -> FirstStep:
    """Judge the first step on ``sentence``: the calls the model made, and its text."""
    names = {call.name for call in calls}
    right = NO_TOOL in sentence.accept if not calls else names <= sentence.accept
    copies = " ".join(
        value for call in calls for value in call.arguments.values() if isinstance(value, str)
    )
    refused = []
    for call in calls:
        verdict = judge(call, (sentence.text,))
        if isinstance(verdict, Misstep):
            refused.append(f"{call.name}: {verdict.kind.value}: {verdict.detail}")
    return FirstStep(
        sentence=sentence,
        calls=tuple(calls),
        text=text,
        right=right,
        words_found=tuple(word for word in sentence.copied if word in copies),
        words_missing=tuple(word for word in sentence.copied if word not in copies),
        refused=tuple(refused),
    )


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _called(calls: Sequence[ToolCall]) -> str:
    if not calls:
        return NO_TOOL
    return "; ".join(
        f"`{call.name}` {json.dumps(dict(call.arguments), ensure_ascii=False)}" for call in calls
    )


def markdown(steps: Sequence[FirstStep], conditions: Mapping[str, object]) -> str:
    """The table of a run, one row a sentence, and the count of first steps right."""
    right = sum(step.right for step in steps)
    lines = [
        f"Model `{conditions['model']}`, prompt `{conditions['prompt']}`: "
        f"first step right on {right} of {len(steps)} sentences.",
        "",
        "| Sentence | Accepted | First step | Right | Expected words copied "
        "| Judged by the program |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step in steps:
        expected = ", ".join(step.words_found) or "-"
        if step.words_missing:
            expected += f" (missing: {', '.join(step.words_missing)})"
        lines.append(
            f"| {step.sentence.id} | {', '.join(sorted(step.sentence.accept))} "
            f"| {_cell(_called(step.calls))} | {'yes' if step.right else 'no'} "
            f"| {_cell(expected)} | {_cell('; '.join(step.refused) or 'taken')} |"
        )
    return "\n".join(lines) + "\n"
