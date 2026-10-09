"""The two ways a run reads a passage that may report several trades.

- ``ONE_LIST``: the whole passage in one call, the model handing back one
  list of rows (``extract``). This is the way the product reads a passage,
  and the way every run made before the two were compared read it.
- ``SPLIT_FIRST``: the passage first split into one segment per trade, then
  each segment extracted on its own (``splitting``).

A run line records its way under ``method``. A run line without it was made
before there was a choice, and read the passage the one-list way
(``method_of``).

Names defined here: ``Method`` and ``method_of``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping


class Method(enum.Enum):
    """How a run reads each passage; the value is its name on the command line and in the files."""

    ONE_LIST = "one_list"
    SPLIT_FIRST = "split_first"


def method_of(run: Mapping[str, object]) -> Method:
    """The way the run whose run line is ``run`` read its passages."""
    return Method(run.get("method", Method.ONE_LIST.value))
