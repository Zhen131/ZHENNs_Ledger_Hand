"""The segments of a passage: the pieces the model copied for each trade, put back together.

``segments_of`` takes the passage and, for each trade, the pieces the model
copied for it (``split_table``), and gives back one segment per trade, or
``PieceMissed``: the first piece that is not a piece of the passage, and
why.

For each trade, in the order given:

1. A piece is taken without its own whitespace at either end; a piece of
   nothing but whitespace is left out.
2. Every other piece is looked up in the passage the way extraction looks up
   a phrase (``Passage.find``): with the same tidying, and only where it
   does not cut a number of the passage in two. It stands for the passage's
   own text there. Where it stands more than once, the first such place is
   taken.
3. The pieces are put in the order they stand in the passage. Pieces that
   overlap, touch, or stand apart by nothing but whitespace and punctuation
   become one run of the passage, what stands between them included.
4. The runs are written out, each as the passage's own text, joined by a
   full-width comma (``SEPARATOR``), so that a segment still reads as one
   passage. (Joined by line breaks, the model took each line for a trade of
   its own.)

So a segment holds nothing but the passage's own characters, with a comma
between two runs that stand apart in the passage; nothing is rewritten. A
trade with no piece left gives no segment.

Names defined here: ``segments_of``, ``PieceMissed`` and ``SEPARATOR``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from ledger_hand.extraction.passage import Passage, PieceMiss

# Between two runs of a segment that stand apart in the passage. A phrase
# the model copies across it is not a piece of the passage, which the reading
# of all the rows against the whole passage finds (``splitting``).
SEPARATOR = "\N{FULLWIDTH COMMA}"


@dataclass(frozen=True)
class PieceMissed:
    """A piece, as the model wrote it, that is not a piece of the passage, and why."""

    piece: str
    miss: PieceMiss


def segments_of(passage: Passage, trades: Sequence[Sequence[str]]) -> tuple[str, ...] | PieceMissed:
    """One segment per trade that has a piece, in the order given; or the first piece missed."""
    segments: list[str] = []
    for pieces in trades:
        spans: list[tuple[int, int]] = []
        for written in pieces:
            if not written.strip():
                continue
            found = passage.find(written.strip())
            if isinstance(found, PieceMiss):
                return PieceMissed(written, found)
            spans.append((found.start, found.end))
        if spans:
            segments.append(_written_out(passage.text, spans))
    return tuple(segments)


def _written_out(text: str, spans: list[tuple[int, int]]) -> str:
    """The runs of ``text`` that ``spans`` cover; one run where only spacing parts two spans."""
    runs: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        # A span that overlaps the run before it gives an empty gap here.
        if runs and _only_spacing(text[runs[-1][1] : start]):
            runs[-1] = (runs[-1][0], max(runs[-1][1], end))
        else:
            runs.append((start, end))
    return SEPARATOR.join(text[start:end] for start, end in runs)


def _only_spacing(gap: str) -> bool:
    """Whether ``gap`` holds nothing but whitespace and punctuation."""
    return all(ch.isspace() or unicodedata.category(ch).startswith("P") for ch in gap)
