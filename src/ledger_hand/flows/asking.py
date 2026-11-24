"""Asking the ledger through the four read tools, narrowed only as far as the user asked.

The assistant's model picks a read tool and copies the user's words for it;
this module turns that into a lookup the ledger can answer, and asks it:

- ``list_assets`` and ``get_positions`` take nothing and are asked as they
  are.
- ``list_trades`` and ``get_period_summary`` may be narrowed by a period,
  an asset and (for trades) a side. The period the model copied is turned
  into days by the program (``core.time_range``); words it cannot read,
  that mean more than one stretch of time, or that lie wholly in the
  future are not guessed at: the ledger is not asked, and the program
  tells the user which words, and why (``ProgramWords``). No period means
  all time. The asset and the side are checked against what the user said
  (``assistant.narrowing``): one the user did not ask for is not used, and
  the header says so; an asset the user named that the ledger does not
  have ends in the program's words as well.

``judge_read`` judges a call to the two narrowed tools: the asset is taken
out first and checked apart, and the rest is judged as any call is
(``assistant.judging``). When the model's period is not the user's words,
or it gave none, the program looks for the time in what the user just said
itself (``core.time_range.find_period_words``): exactly one found is used,
is no wrong step, and the header says the time was taken from the user's
words; more than one found is a wrong step when the model gave a period,
and a question to the user when it gave none; none found is a wrong step
when the model gave a period, and all time when it gave none. Exactly one
found is used whatever the model gave, even words copied right from the
sentence before: what the user says now comes first, as with the asset.
With none or several found, a period the model copied right is used as it
is. (Decided on 2026-11-24.)

Every figure in a ``Lookup`` is the ledger's own. This module reads no
clock, no zone of the machine and no settings: all are handed in.

Names defined here: ``READ_TOOLS``, ``NARROWED_TOOLS``, ``ProgramWords``,
``ReadVerdict``, ``judge_read`` and ``look_up``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant.judging import Accepted, Misstep, MisstepKind, judge
from ledger_hand.assistant.lookups import Conditions, Lookup, latest_trades
from ledger_hand.assistant.narrowing import (
    AssetDropped,
    AssetUsed,
    NoSuchAsset,
    SideDropped,
    check_asset,
    check_side,
)
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import PeriodRequest, TradeFilter
from ledger_hand.core.time_range import (
    Period,
    PeriodRefusal,
    PeriodRefused,
    find_period_words,
    read_period,
)
from ledger_hand.core.trade import Side
from ledger_hand.ports import LedgerPort, ToolCall

READ_TOOLS = frozenset(
    {
        ToolName.LIST_ASSETS,
        ToolName.LIST_TRADES,
        ToolName.GET_PERIOD_SUMMARY,
        ToolName.GET_POSITIONS,
    }
)
NARROWED_TOOLS = frozenset({ToolName.LIST_TRADES.value, ToolName.GET_PERIOD_SUMMARY.value})

_PERIOD_WORDS = {
    PeriodRefusal.UNKNOWN_WORDING: (
        "I could not read {word!r} as a stretch of time, so I looked nothing up. "
        "Please say it another way, such as '10月', 'last week' or '最近7天'."
    ),
    PeriodRefusal.AMBIGUOUS: (
        "{word!r} can mean more than one stretch of time, so I looked nothing up. "
        "Please say which one, with the year, such as '2025年12月'."
    ),
    PeriodRefusal.IN_THE_FUTURE: (
        "{word!r} lies in the future, so there is nothing in the ledger to look up yet."
    ),
}
_MANY_PERIODS = (
    "You named more than one stretch of time ({words}), so I looked nothing up. "
    "Please ask about one of them."
)
_NO_SUCH_ASSET = "The ledger has no asset called {word!r}, so I looked nothing up."


@dataclass(frozen=True)
class ProgramWords:
    """The program answers the user itself, and the ledger is not asked."""

    words: str


@dataclass(frozen=True)
class ReadVerdict:
    """A call to a narrowed tool judged: the verdict, the model's asset apart, and the period
    the program took from the user's words in place of the model's, if it took one."""

    verdict: Accepted | Misstep
    asset: str | None = None
    period_found: str | None = None


def judge_read(
    call: ToolCall, user_said: Sequence[str], *, now: datetime, zone: str
) -> ReadVerdict:
    """Judge a call to a narrowed tool with its asset taken out; the asset comes back apart.

    An asset that is not text is left in, so that the judging still calls
    it a wrong step; a blank one counts as not given. When exactly one
    stretch of time is found in what the user just said, it takes the place
    of the model's period, whatever that was; otherwise a period that is not
    the user's words stays a wrong step, and one that is is used.
    """
    arguments = dict(call.arguments)
    asset = arguments.get("asset")
    if asset is not None and not isinstance(asset, str):
        return ReadVerdict(verdict=judge(call, user_said))
    arguments.pop("asset", None)
    kept = asset if asset is not None and asset.strip() else None
    verdict = judge(ToolCall(name=call.name, arguments=arguments), user_said)
    given = arguments.get("period")
    if not isinstance(given, str) or not given.strip():
        return ReadVerdict(verdict=verdict, asset=kept)
    found = find_period_words(user_said[-1], now, zone)
    if len(found) != 1 or (found[0] == given and not _period_not_copied(verdict)):
        return ReadVerdict(verdict=verdict, asset=kept)
    arguments["period"] = found[0]
    again = judge(ToolCall(name=call.name, arguments=arguments), user_said)
    if isinstance(again, Misstep):
        return ReadVerdict(verdict=verdict, asset=kept)
    return ReadVerdict(verdict=again, asset=kept, period_found=found[0])


def _period_not_copied(verdict: Accepted | Misstep) -> bool:
    """Whether the verdict is a wrong step for a period that is not the user's words."""
    return (
        isinstance(verdict, Misstep)
        and verdict.kind is MisstepKind.NOT_COPIED
        and verdict.detail.startswith("'period' is ")
    )


@dataclass(frozen=True)
class _Said:
    """What the user said just now, what they said the time before, and when and where."""

    now_words: str
    before: str | None
    now: datetime
    zone: str


def look_up(
    accepted: Accepted,
    asset: str | None,
    ledger: LedgerPort,
    user_said: Sequence[str],
    *,
    now: datetime,
    zone: str,
    period_found: str | None = None,
) -> Lookup | ProgramWords:
    """Ask the ledger what the read tool of ``accepted`` asks; ``asset`` as the model gave it.

    ``period_found`` is the period the program took from the user's words in
    place of the model's (``judge_read``).
    """
    if accepted.tool is ToolName.GET_POSITIONS:
        return Lookup(tool=accepted.tool, positions=ledger.positions())
    if accepted.tool is ToolName.LIST_ASSETS:
        return Lookup(tool=accepted.tool, assets=ledger.list_assets())
    said = _Said(user_said[-1], user_said[-2] if len(user_said) > 1 else None, now, zone)
    conditions = _conditions(accepted, asset, ledger, said, period_found)
    if isinstance(conditions, ProgramWords):
        return conditions
    period = conditions.period
    start, end = (period.start, period.end) if period is not None else (None, None)
    if accepted.tool is ToolName.GET_PERIOD_SUMMARY:
        request = PeriodRequest(start=start, end=end, asset=conditions.asset)
        summary = ledger.period_summary(request)
        return Lookup(
            tool=accepted.tool,
            conditions=conditions,
            summary=summary,
            trade_count=summary.trade_count,
        )
    trade_filter = TradeFilter(start=start, end=end, asset=conditions.asset, side=conditions.side)
    trades = ledger.list_trades(trade_filter)
    return Lookup(
        tool=accepted.tool,
        conditions=conditions,
        trades=latest_trades(trades),
        trade_count=len(trades),
    )


def _period(
    accepted: Accepted, said: _Said, period_found: str | None
) -> tuple[Period | None, str | None] | ProgramWords:
    """The period to look up with, and the user's words it was taken from by the program.

    The model's period, when it is the user's words, is used as it stands.
    With none from the model, the one stretch of time in what the user just
    said is taken; with more than one there, the user is asked which.
    """
    words = period_found or accepted.arguments.get("period")
    if words is None:
        found = find_period_words(said.now_words, said.now, said.zone)
        if len(found) > 1:
            return ProgramWords(_MANY_PERIODS.format(words=", ".join(map(repr, found))))
        if not found:
            return None, None
        words = period_found = found[0]
    reading = read_period(words, said.now, said.zone)
    if isinstance(reading, PeriodRefused):
        return ProgramWords(_PERIOD_WORDS[reading.reason].format(word=words))
    return reading, period_found


def _conditions(
    accepted: Accepted,
    asset: str | None,
    ledger: LedgerPort,
    said: _Said,
    period_found: str | None,
) -> Conditions | ProgramWords:
    """The period, asset and side to look up with, or the program's words instead."""
    not_narrowed: list[str] = []
    settled = _period(accepted, said, period_found)
    if isinstance(settled, ProgramWords):
        return settled
    period, taken_from = settled
    code: str | None = None
    if asset is not None:
        checked = check_asset(asset, ledger.list_assets(), said.now_words, said.before)
        if isinstance(checked, NoSuchAsset):
            return ProgramWords(_NO_SUCH_ASSET.format(word=checked.word))
        if isinstance(checked, AssetDropped):
            not_narrowed.append(checked.why)
        if isinstance(checked, AssetUsed):
            code = checked.code
    side: Side | None = None
    given_side = accepted.arguments.get("side")
    if accepted.tool is ToolName.LIST_TRADES and given_side is not None:
        side_checked = check_side(given_side, said.now_words, said.before)
        if isinstance(side_checked, SideDropped):
            not_narrowed.append(side_checked.why)
        else:
            side = side_checked.side
    return Conditions(
        period=period,
        period_words=taken_from,
        asset=code,
        side=side,
        not_narrowed=tuple(not_narrowed),
    )
