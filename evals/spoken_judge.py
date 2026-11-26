"""How one sentence said the owner's way came out: each gold trade judged into exactly one ending.

``spoken_run`` turns what came of a sentence into an ``Observed``: the
trades sent (``SentTrade``, each with the values it reached the ledger
with and the cells that carried a mark of their own), the question left
waiting (``Waiting``) with the drafts as they stood, the reasons nothing
was sent, and whether the model could be reached at all. ``judge``
compares it with the sentence's gold answer and gives one ``TradeResult``
for each gold trade, and one for each trade sent beyond them:

- ``CLEAN`` (①): sent, every judged cell the gold one, and the gold trade
  has no cell that is none or suspect;
- ``EMPTY_LEFT`` (①b): sent, its none cells left empty, every other cell
  right (only once the ledger takes a card with empty cells);
- ``MARKED`` (②): sent, some cell not the gold one, but every such cell,
  every suspect cell and every none cell filled carries its own mark;
- ``SILENT`` (③): sent, and some cell that is wrong, suspect, or none but
  filled carries no mark of its own; a trade sent beyond the gold ones
  counts every cell as wrong;
- ``ASKED_OK``, ``ASKED_NOT_OK`` (④): nothing sent, the question waits,
  and it is about this trade; about a cell the gold lets be asked, or not.
  A cell the gold lets be asked is one its ``ask_ok`` names; when it names
  none, every none and suspect cell, but only the asset and buy or sell
  once the ledger takes a card with empty cells (``Observed.cards``, read
  from the flow's own setting): then every other gap is sent, not asked
  (``ASKED_ONCE_CARDS_ARE_TAKEN``, the contract of 2026-11-25);
- ``NOT_ITS_TURN`` (④): nothing sent, a question waits about another trade;
- ``NOT_SENT`` (⑤): nothing sent and nothing waits, for the reasons given;
- ``NOT_MEASURED``: the model could not be reached, twice.

A trade whose gold answer holds a rate (a trade paid in another money
than its asset's own, ``GoldRate``) also has its rate judged, as the cell
``cost_rate``: wrong when none was sent or it is more than a ten-thousandth
of it away (``RATE_TOLERANCE``); its own mark is the card's, suspicious or
assumed. A trade with no rate in its gold answer has none judged.

A cell's own mark is one of: a reminder the reply said, about this trade
and this cell (``evals.cells.issues_about``); the mark that its money was
guessed (the pricing money, the fee's money); the line saying the model
picked the asset from the ledger's list (the asset alone); a mark on the
card the trade was sent as, suspicious or assumed (``spoken_run``). What
the program worked out is no mark.

For a trade asked about, or waiting its turn, the draft as it stands is
also compared with every gold cell that has a value (computed, none and
skipped cells left aside, the cells asked about too, and cells still
empty): a cell another value than the gold one with no mark (the
reminders that will be said once it is sent, or the mark of a guess) is
counted apart (``draft_unmarked``), since the user's answer sends the
draft as it is; it is not a ③.

A sentence not enabled has no gold trade: anything it sends is judged as
trades beyond the gold ones; otherwise it said it cannot be recorded, it
asked, or something else (``disabled_ending``).

Names defined here: ``ASKED_ONCE_CARDS_ARE_TAKEN``, ``RATE_CELL``, ``RATE_TOLERANCE``,
``Ending``, ``SentTrade``,
``Waiting``, ``Observed``, ``TradeResult``, ``judge``, ``disabled_ending``, ``first_tool_right`` and
``same_value``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from evals.cells import tidy_text
from evals.spoken_set import (
    CELLS,
    SEND,
    GoldTrade,
    SpokenSentence,
    gold_moment,
    gold_value,
)

# The only cells a question is rightly about, by default, once the ledger takes
# a card with empty cells: the ledger takes neither empty (81A section 2 item 1).
ASKED_ONCE_CARDS_ARE_TAKEN = frozenset({"asset", "side"})


class Ending(enum.Enum):
    CLEAN = "1 saved with no cell changed"
    EMPTY_LEFT = "1b sent with its none cells empty"
    MARKED = "2 sent, every wrong cell marked"
    SILENT = "3 a wrong figure with no mark"
    ASKED_OK = "4 asked, rightly"
    ASKED_NOT_OK = "4 asked, not rightly"
    NOT_ITS_TURN = "4 another trade asked about"
    NOT_SENT = "5 not sent"
    NOT_MEASURED = "not measured"


@dataclass(frozen=True)
class SentTrade:
    """One trade that reached the ledger.

    ``number`` is its place in what was said, from 1; ``values`` its ten
    cells as text (a moment as local time to the minute, ``None`` for a
    time known only to the day); ``marked`` the cells with a mark of their
    own, of any kind; ``picked_only`` the cells whose only mark is the
    line about an asset the model picked; ``inferred`` the cells marked as
    a guessed money; ``day`` the day of a time known only to the day;
    ``cost_rate`` the rate it was sent with, or ``None``.
    """

    number: int
    values: Mapping[str, str | None]
    marked: frozenset[str] = frozenset()
    picked_only: frozenset[str] = frozenset()
    inferred: frozenset[str] = frozenset()
    day: str | None = None
    cost_rate: str | None = None


@dataclass(frozen=True)
class Waiting:
    """The question left waiting: the trade it is about (from 0), the cells asked, the drafts.

    ``drafts`` holds, for each trade's place (from 0), its cells that have a
    value, as text, and ``draft_marked`` the cells of each with a mark.
    """

    trade: int
    cells: frozenset[str]
    drafts: Mapping[int, Mapping[str, str]] = field(default_factory=dict)
    draft_marked: Mapping[int, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Observed:
    """What came of one sentence, in the shape ``judge`` reads.

    ``passage_reminders`` says the reply held a reminder about the passage
    as a whole; ``answered`` the trades (from 0) whose asset the ruler
    answered with its code once; ``cards`` that the ledger took a card with
    empty cells, so only the asset and buy or sell are rightly asked.
    """

    sent: tuple[SentTrade, ...] = ()
    waiting: Waiting | None = None
    reasons: frozenset[str] = frozenset()
    passage_reminders: bool = False
    answered: frozenset[int] = frozenset()
    model_unreachable: bool = False
    cards: bool = False


@dataclass(frozen=True)
class TradeResult:
    """One gold trade (or one trade sent beyond them) and how it came out.

    ``trade`` is the gold trade's place, from 0, or ``None`` for one sent
    beyond them; ``wrong`` the cells that are not the gold ones; ``unmarked``
    those of them, and of the suspect and filled none cells, with no mark;
    ``picked_saved`` says only the picked-asset line kept it out of ③;
    ``guess_missing`` the cells that should be marked as a guess and are
    not; ``draft_unmarked`` the draft's cells another value with no mark.
    """

    trade: int | None
    ending: Ending
    wrong: frozenset[str] = frozenset()
    unmarked: frozenset[str] = frozenset()
    picked_saved: bool = False
    guess_missing: frozenset[str] = frozenset()
    draft_unmarked: frozenset[str] = frozenset()
    answered: bool = False


_NUMBER_CELLS = frozenset({"quantity", "price", "total", "fee"})


def same_value(name: str, gold: str, got: str | None) -> bool:
    """Whether ``got`` is the gold value of the cell ``name``: numbers by value, text tidied."""
    if got is None:
        return False
    if name in _NUMBER_CELLS:
        return Decimal(gold) == Decimal(got)
    if name == "platform":
        return tidy_text(gold) == tidy_text(got)
    return gold == got


# The name of a trade's rate among the cells judged, when its gold answer holds one.
RATE_CELL = "cost_rate"
# How far apart a rate and the gold one may be, relatively: a ten-thousandth (87B,
# part 6, the second part's line, 2026-11-25).
RATE_TOLERANCE = Decimal("0.0001")


def _wrong_rate(gold: GoldTrade, sent: SentTrade) -> frozenset[str]:
    """``RATE_CELL`` when the gold answer holds a rate and the one sent is not it, within
    ``RATE_TOLERANCE`` of it; nothing otherwise."""
    rate = gold.cost_rate
    if rate is None:
        return frozenset()
    got = sent.cost_rate
    if got is not None and abs(Decimal(got) / Decimal(rate.value) - 1) <= RATE_TOLERANCE:
        return frozenset()
    return frozenset({RATE_CELL})


def local_minute(moment: datetime, zone: str) -> str:
    """A moment as local time in ``zone``, to the minute, as gold times are written."""
    return moment.astimezone(ZoneInfo(zone)).strftime("%Y-%m-%d %H:%M")


def _expected(gold: GoldTrade, name: str, zone: str) -> str | None:
    value = gold_value(gold, name)
    if value is None or name != "occurred":
        return value
    return local_minute(gold_moment(value, zone), zone)


def _sent_result(
    index: int, gold: GoldTrade, sent: SentTrade, zone: str, *, answered: bool
) -> TradeResult:
    wrong: set[str] = set(_wrong_rate(gold, sent))
    must_mark: set[str] = set(gold.suspect)
    empty_ok = True
    for name in CELLS:
        cell = gold.cells[name]
        if cell.skip:
            continue
        got = sent.values.get(name)
        if cell.none:
            if got is None and (name != "occurred" or sent.day == cell.day):
                continue
            empty_ok = False
            wrong.add(name)
            continue
        expected = _expected(gold, name, zone)
        if expected is None or not same_value(name, expected, got):
            wrong.add(name)
    must_mark |= wrong
    unmarked = frozenset(must_mark - sent.marked)
    without_pick = frozenset(must_mark - (sent.marked - sent.picked_only))
    guess_missing = frozenset(gold.inferred - sent.inferred)
    if unmarked:
        ending = Ending.SILENT
    elif not wrong and not gold.suspect and gold.clean:
        ending = Ending.CLEAN
    elif not wrong and not gold.suspect and empty_ok:
        ending = Ending.EMPTY_LEFT
    else:
        ending = Ending.MARKED
    return TradeResult(
        trade=index,
        ending=ending,
        wrong=frozenset(wrong),
        unmarked=unmarked,
        picked_saved=not unmarked and bool(without_pick),
        guess_missing=guess_missing,
        answered=answered,
    )


def _extra_result(sent: SentTrade) -> TradeResult:
    every = frozenset(CELLS)
    unmarked = every - sent.marked
    without_pick = every - (sent.marked - sent.picked_only)
    return TradeResult(
        trade=None,
        ending=Ending.SILENT if unmarked else Ending.MARKED,
        wrong=every,
        unmarked=unmarked,
        picked_saved=not unmarked and bool(without_pick),
    )


def _draft_unmarked(index: int, gold: GoldTrade, waiting: Waiting, zone: str) -> frozenset[str]:
    draft = waiting.drafts.get(index, {})
    marked = waiting.draft_marked.get(index, frozenset())
    asked = waiting.cells if waiting.trade == index else frozenset()
    found: set[str] = set()
    for name in CELLS:
        cell = gold.cells[name]
        if cell.value is None or name in asked or name not in draft:
            continue
        expected = _expected(gold, name, zone)
        if (
            expected is not None
            and not same_value(name, expected, draft[name])
            and name not in marked
        ):
            found.add(name)
    return frozenset(found)


def _waiting_result(
    index: int, gold: GoldTrade, waiting: Waiting, zone: str, *, answered: bool, cards: bool
) -> TradeResult:
    askable = gold.askable
    if cards and not gold.ask_ok:
        askable = ASKED_ONCE_CARDS_ARE_TAKEN
    if waiting.trade != index:
        ending = Ending.NOT_ITS_TURN
    elif waiting.cells & askable:
        ending = Ending.ASKED_OK
    else:
        ending = Ending.ASKED_NOT_OK
    return TradeResult(
        trade=index,
        ending=ending,
        draft_unmarked=_draft_unmarked(index, gold, waiting, zone),
        answered=answered,
    )


def judge(sentence: SpokenSentence, observed: Observed, zone: str) -> list[TradeResult]:
    """One result for each gold trade of ``sentence``, then one for each trade sent beyond them."""
    golds = sentence.gold.trades if sentence.gold.expect == SEND else ()
    if observed.model_unreachable:
        return [TradeResult(trade=index, ending=Ending.NOT_MEASURED) for index in range(len(golds))]
    results: list[TradeResult] = []
    by_place = {one.number - 1: one for one in observed.sent if one.number - 1 < len(golds)}
    for index, gold in enumerate(golds):
        answered = index in observed.answered
        if index in by_place:
            results.append(_sent_result(index, gold, by_place[index], zone, answered=answered))
        elif observed.waiting is not None:
            results.append(
                _waiting_result(
                    index, gold, observed.waiting, zone, answered=answered, cards=observed.cards
                )
            )
        else:
            results.append(TradeResult(trade=index, ending=Ending.NOT_SENT, answered=answered))
    results.extend(_extra_result(one) for one in observed.sent if one.number - 1 >= len(golds))
    return results


class DisabledEnding(enum.Enum):
    TOLD = "said it cannot be recorded"
    ASKED = "asked"
    SENT = "sent"
    OTHER = "something else"


def disabled_ending(sentence: SpokenSentence, observed: Observed) -> DisabledEnding | None:
    """How a sentence not enabled came out; ``None`` for an enabled one or one not measured."""
    if sentence.enabled or observed.model_unreachable:
        return None
    if observed.sent:
        return DisabledEnding.SENT
    if observed.waiting is not None:
        return DisabledEnding.ASKED
    if observed.reasons and observed.reasons <= sentence.gold.why:
        return DisabledEnding.TOLD
    return DisabledEnding.OTHER


def first_tool_right(first_tool: str | None) -> bool:
    """Whether the first tool the model called for a recording sentence was the one to record."""
    return first_tool == "propose_trade_add"
