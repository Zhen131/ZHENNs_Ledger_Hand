"""The record of every reply read for one passage, matched to the drafts it made.

A sentence line of a results file holds the model's raw replies and, under
``copied``, the phrases the model wrote for each draft. With one call per
passage those are the rows of the last reply; when a passage is split first,
the drafts come from several replies, one per segment, and the last reply
alone would hold the phrases of the last segment only. So a line also holds
``reads``: one entry per call, in the order made, with

- ``call``: its place among the calls, counting from 0;
- ``step``: what it was for, ``split`` or ``extract``;
- ``segment``: the segment an extraction read, counting from 0, or ``null``
  for the whole passage, and for the split;
- for an extraction, ``rows``: the phrases of every row of the reply that is
  not empty, by field, as the model wrote them, or ``null`` when the reply
  could not be read as the table; and ``drafts``: for each of those rows, the
  place among the passage's drafts of the draft it became, or nothing when
  the drafts were not made from this reply.

``reads_of`` builds the entries; ``copied_from_reads`` gives back the phrases
of each draft in the order of the drafts. The scoring reads a line's phrases
from its ``reads`` when it has them (``records.produced_from_line``); a line
written before ``reads`` existed has none, and its ``copied`` is read as it
always was.

Names defined here: ``reads_of`` and ``copied_from_reads``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ledger_hand.extraction.reply_parser import ReplyRows, read_reply
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.splitting import CallStep, Purpose
from ledger_hand.ports import ModelReply


def reads_of(
    replies: Sequence[ModelReply], steps: Sequence[CallStep], draft_calls: Sequence[int]
) -> list[dict[str, object]]:
    """One entry per reply, in order; ``draft_calls`` are the replies the drafts were made from."""
    if len(replies) != len(steps):
        raise ValueError("one step per reply")
    entries: list[dict[str, object]] = []
    made = 0
    for at, (reply, step) in enumerate(zip(replies, steps, strict=True)):
        entry: dict[str, object] = {
            "call": at,
            "step": step.purpose.value,
            "segment": step.segment,
        }
        if step.purpose is Purpose.EXTRACT:
            rows = _rows(reply)
            entry["rows"] = rows
            count = len(rows) if rows is not None and at in draft_calls else 0
            entry["drafts"] = list(range(made, made + count))
            made += count
        entries.append(entry)
    return entries


def _rows(reply: ModelReply) -> list[dict[str, str]] | None:
    read = read_reply(reply)
    if not isinstance(read, ReplyRows):
        return None
    return [
        {field.value: text for field, text in row.cells.items()}
        for row in read.rows
        if not row.is_empty
    ]


def copied_from_reads(reads: object) -> tuple[Mapping[Field, str], ...]:
    """The phrases of each draft, by field, in the order of the drafts, as ``reads`` holds them."""
    if not isinstance(reads, list):
        raise ValueError("the reads are a list")
    placed: dict[int, Mapping[Field, str]] = {}
    for entry in reads:
        rows = entry.get("rows") or []
        drafts = entry.get("drafts") or []
        if drafts and len(drafts) != len(rows):
            raise ValueError(f"call {entry.get('call')}: not one draft per row")
        for at, row in zip(drafts, rows, strict=False):
            placed[int(at)] = {Field(name): str(text) for name, text in row.items()}
    if sorted(placed) != list(range(len(placed))):
        raise ValueError("the drafts of the reads are not counted from 0 without a gap")
    return tuple(placed[at] for at in range(len(placed)))
