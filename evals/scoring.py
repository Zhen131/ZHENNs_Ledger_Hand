"""The scores: one passage judged against its gold answer, and many passages added up.

``score_sentence`` takes a sentence and what extraction produced for it (a
``Produced``) and gives a ``SentenceScore``: whether the reply could be
read, the pairing of drafts with gold trades (``matching``), and every
field of every pair judged (``cells``). ``add_up`` adds sentence scores into
``Scores``. Both are pure: they read nothing and write nothing.

The five scores, each with what it is divided by:

- **well-formed rate**: sentences whose reply was read as the table, divided
  by all sentences. A reply that missed the table on every try, and a model
  failure of any kind, count against it: no table was read either way;
- **per field**: for each scored field, the pairs in which it came out
  right, divided by the pairs;
- **whole trades right** (the main score): pairs in which all eleven fields
  came out right (an empty gold field must be empty too), divided by the
  gold trades. A missed trade counts as wrong;
- **missed and extra**: per sentence, gold trades minus drafts when that is
  above zero, and drafts minus gold trades when that is above zero; added up;
- **made-up rate**: fields in pairs where the gold value is empty and the
  draft holds one, divided by the fields in pairs where the gold value is
  empty;
- and for passages with no trade: sentences whose reply was read and gave no
  draft, divided by such sentences.

Sentences of the ``not_to_record`` group are scored by none of these; the
caller keeps them apart (``tables``).

Names defined here: ``ResultKind``, ``Produced``, ``PairScore``,
``SentenceScore``, ``Scores``, ``score_sentence`` and ``add_up``.
"""

from __future__ import annotations

import collections
import enum
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from evals.cells import (
    SCORED_FIELDS,
    CellOutcome,
    CellResult,
    EmptyReason,
    draft_value,
    issues_about,
    judge_cell,
)
from evals.gold import Sentence
from evals.matching import pair_trades
from ledger_hand.core.trade import TradeDraft
from ledger_hand.extraction.issues import Issue
from ledger_hand.extraction.reply_table import Field


class ResultKind(enum.Enum):
    """What extraction gave for a passage."""

    EXTRACTED = "extracted"
    REPLY_UNREADABLE = "reply_unreadable"
    MODEL_FAILED = "model_failed"
    PASSAGE_REFUSED = "passage_refused"


@dataclass(frozen=True)
class Produced:
    """What extraction gave for one passage, as the scorer needs it.

    ``copied`` holds, for each draft, the phrases the model wrote for it, by
    field; a field it left empty is left out.
    """

    kind: ResultKind
    drafts: tuple[TradeDraft, ...] = ()
    issues: tuple[Issue, ...] = ()
    copied: tuple[Mapping[Field, str], ...] = ()


@dataclass(frozen=True)
class PairScore:
    """One gold trade and the draft paired with it, field by field."""

    gold_at: int
    draft_at: int
    cells: tuple[CellResult, ...]

    @property
    def whole(self) -> bool:
        """Whether every field came out right."""
        return all(cell.outcome is CellOutcome.RIGHT for cell in self.cells)


@dataclass(frozen=True)
class SentenceScore:
    """One sentence judged against its gold answer."""

    sentence_id: str
    kind: ResultKind
    gold_trades: int
    drafts: int
    pairs: tuple[PairScore, ...]
    missed: int
    extra: int

    @property
    def well_formed(self) -> bool:
        """Whether the reply was read as the table."""
        return self.kind is ResultKind.EXTRACTED

    @property
    def whole_right(self) -> int:
        """How many gold trades came out right in every field."""
        return sum(pair.whole for pair in self.pairs)


def score_sentence(sentence: Sentence, produced: Produced) -> SentenceScore:
    """``produced`` judged against the gold answer of ``sentence``."""
    pairing = pair_trades(sentence.trades, produced.drafts)
    pairs: list[PairScore] = []
    for gold_at, draft_at in pairing.pairs:
        gold = sentence.trades[gold_at]
        draft = produced.drafts[draft_at]
        copied = produced.copied[draft_at] if draft_at < len(produced.copied) else {}
        cells = tuple(
            judge_cell(
                name,
                gold.cell(name),
                draft_value(draft, name),
                issues_about(name, draft_at, produced.issues),
                copied.get(name),
            )
            for name in SCORED_FIELDS
        )
        pairs.append(PairScore(gold_at, draft_at, cells))
    return SentenceScore(
        sentence_id=sentence.id,
        kind=produced.kind,
        gold_trades=len(sentence.trades),
        drafts=len(produced.drafts),
        pairs=tuple(pairs),
        missed=len(pairing.missed),
        extra=len(pairing.extra),
    )


@dataclass
class Scores:
    """Sentence scores added up; every ratio is kept as its two counts."""

    sentences: int = 0
    well_formed: int = 0
    gold_trades: int = 0
    drafts: int = 0
    pairs: int = 0
    whole_right: int = 0
    missed: int = 0
    extra: int = 0
    gold_empty_fields: int = 0
    made_up_fields: int = 0
    no_trade_sentences: int = 0
    no_trade_right: int = 0
    field_right: collections.Counter[Field] = field(default_factory=collections.Counter)
    outcomes: collections.Counter[CellOutcome] = field(default_factory=collections.Counter)
    empty_reasons: collections.Counter[EmptyReason] = field(default_factory=collections.Counter)
    half_copies: collections.Counter[CellOutcome] = field(default_factory=collections.Counter)


def add_up(scores: Iterable[SentenceScore]) -> Scores:
    """The sentence scores ``scores`` added up."""
    total = Scores()
    for score in scores:
        total.sentences += 1
        total.well_formed += score.well_formed
        total.gold_trades += score.gold_trades
        total.drafts += score.drafts
        total.pairs += len(score.pairs)
        total.whole_right += score.whole_right
        total.missed += score.missed
        total.extra += score.extra
        if score.gold_trades == 0:
            total.no_trade_sentences += 1
            total.no_trade_right += score.well_formed and score.drafts == 0
        for pair in score.pairs:
            _add_pair(total, pair)
    return total


def _add_pair(total: Scores, pair: PairScore) -> None:
    for cell in pair.cells:
        total.outcomes[cell.outcome] += 1
        if cell.outcome is CellOutcome.RIGHT:
            total.field_right[cell.field] += 1
        if cell.gold is None:
            total.gold_empty_fields += 1
            total.made_up_fields += cell.outcome is CellOutcome.MADE_UP
        if cell.reason is not None:
            total.empty_reasons[cell.reason] += 1
        if cell.half_copy:
            total.half_copies[cell.outcome] += 1
