"""The names set: sentences naming a share or a coin the way people say it, and the judging.

The set, ``evals/sets/stock_names.json``, holds sentences that each buy one
asset, said against the demo book (``ledger.demo_book``) at the set's fixed
moment and zone. Each names its group, its half and its gold answer,
written before any run and never changed:

- ``on_list``: the demo book holds the asset; ``gold`` is its code;
- ``off_list``: it does not; ``gold`` is null, and no asset may be picked,
  named or sent.

``words`` are the words that name the asset, for the direct measure.
``half`` is ``practice`` (odd numbers of each group) or ``locked`` (even
numbers): prompts are tuned and chosen on the practice half only, and the
locked half is measured once, after the choice.

Each sentence gets one verdict (``Verdict``):

- ``RIGHT``: on the list, the asset picked, or found by the table, is the
  gold one and no other asset was picked, named or sent; off the list,
  none was;
- ``WRONG``: an asset that is not the gold one was picked, named as the
  trade's asset, or sent; off the list, any asset at all;
- ``NOT_MATCHED``: on the list, nothing was picked or found, and nothing
  wrong was done: the program asks, or says the ledger lacks it;
- ``NOT_MEASURED``: the model failed twice; it counts nowhere.

The pass lines, on the locked half: no sentence ``WRONG`` in
either measure or group; on the list, measured directly, at least
``RIGHT_SHARE`` of the sentences handed to the model ``RIGHT``.

Names defined here: ``NAMES_SET``, ``RIGHT_SHARE``, ``NOT_MEASURED_SHARE``,
``Group``, ``Half``, ``NameSentence``, ``NameSet``, ``load_name_set``,
``Verdict``, ``judge`` and ``counts``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

NAMES_SET = Path(__file__).resolve().parent / "sets" / "stock_names.json"
# Nine in ten, as the measures before took; not measured.
RIGHT_SHARE = Decimal("0.9")
# More than one in ten not measured in a group voids the run.
NOT_MEASURED_SHARE = Decimal("0.1")


class Group(enum.Enum):
    """Whether the demo book holds the asset named."""

    ON_LIST = "on_list"
    OFF_LIST = "off_list"


class Half(enum.Enum):
    """Which half of the set a sentence belongs to."""

    PRACTICE = "practice"
    LOCKED = "locked"


@dataclass(frozen=True)
class NameSentence:
    """One sentence of the set, with its words for the asset and its gold code (or none)."""

    id: str
    group: Group
    kind: str
    half: Half
    text: str
    words: str
    gold: str | None


@dataclass(frozen=True)
class NameSet:
    """The sentences, the moment they are said at, and the zone."""

    now: datetime
    zone: str
    sentences: tuple[NameSentence, ...]


def load_name_set(path: Path = NAMES_SET) -> NameSet:
    """Read the set; a sentence whose gold does not fit its group raises ``ValueError``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sentences = tuple(
        NameSentence(
            id=one["id"],
            group=Group(one["group"]),
            kind=one["kind"],
            half=Half(one["half"]),
            text=one["text"],
            words=one["words"],
            gold=one["gold"],
        )
        for one in data["sentences"]
    )
    for sentence in sentences:
        if (sentence.gold is None) != (sentence.group is Group.OFF_LIST):
            raise ValueError(f"{sentence.id}: the gold does not fit the group")
    return NameSet(datetime.fromisoformat(data["now"]), data["zone"], sentences)


class Verdict(enum.Enum):
    """What came of one sentence, judged against its gold answer."""

    RIGHT = "right"
    WRONG = "wrong"
    NOT_MATCHED = "not matched"
    NOT_MEASURED = "not measured"


def judge(sentence: NameSentence, assets: Iterable[str]) -> Verdict:
    """The verdict, from every asset picked, named or sent for ``sentence``."""
    found = set(assets)
    if sentence.gold is None:
        return Verdict.WRONG if found else Verdict.RIGHT
    if found - {sentence.gold}:
        return Verdict.WRONG
    return Verdict.RIGHT if sentence.gold in found else Verdict.NOT_MATCHED


def counts(verdicts: Iterable[Verdict]) -> dict[str, int]:
    """How many of each verdict, by name."""
    seen = list(verdicts)
    return {verdict.name.lower(): seen.count(verdict) for verdict in Verdict}
