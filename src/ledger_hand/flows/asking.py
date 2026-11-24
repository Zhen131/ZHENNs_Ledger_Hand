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
(``assistant.judging``), so the period must still be the user's own words.

Every figure in a ``Lookup`` is the ledger's own. This module reads no
clock, no zone of the machine and no settings: all are handed in.

Names defined here: ``READ_TOOLS``, ``NARROWED_TOOLS``, ``ProgramWords``,
``judge_read`` and ``look_up``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant.judging import Accepted, Misstep, judge
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
from ledger_hand.core.time_range import Period, PeriodRefusal, PeriodRefused, read_period
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
_NO_SUCH_ASSET = "The ledger has no asset called {word!r}, so I looked nothing up."


@dataclass(frozen=True)
class ProgramWords:
    """The program answers the user itself, and the ledger is not asked."""

    words: str


def judge_read(call: ToolCall, user_said: Sequence[str]) -> tuple[Accepted | Misstep, str | None]:
    """Judge a call to a narrowed tool with its asset taken out; the asset comes back apart.

    An asset that is not text is left in, so that the judging still calls
    it a wrong step; a blank one counts as not given.
    """
    arguments = dict(call.arguments)
    asset = arguments.get("asset")
    if not isinstance(asset, str):
        return judge(call, user_said), None
    del arguments["asset"]
    verdict = judge(ToolCall(name=call.name, arguments=arguments), user_said)
    return verdict, (asset if asset.strip() else None)


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
) -> Lookup | ProgramWords:
    """Ask the ledger what the read tool of ``accepted`` asks; ``asset`` as the model gave it."""
    if accepted.tool is ToolName.GET_POSITIONS:
        return Lookup(tool=accepted.tool, positions=ledger.positions())
    if accepted.tool is ToolName.LIST_ASSETS:
        return Lookup(tool=accepted.tool, assets=ledger.list_assets())
    said = _Said(user_said[-1], user_said[-2] if len(user_said) > 1 else None, now, zone)
    conditions = _conditions(accepted, asset, ledger, said)
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


def _conditions(
    accepted: Accepted, asset: str | None, ledger: LedgerPort, said: _Said
) -> Conditions | ProgramWords:
    """The period, asset and side to look up with, or the program's words instead."""
    not_narrowed: list[str] = []
    period: Period | None = None
    words = accepted.arguments.get("period")
    if words is not None:
        reading = read_period(words, said.now, said.zone)
        if isinstance(reading, PeriodRefused):
            return ProgramWords(_PERIOD_WORDS[reading.reason].format(word=words))
        period = reading
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
        side_checked = check_side(given_side, said.now_words)
        if isinstance(side_checked, SideDropped):
            not_narrowed.append(side_checked.why)
        else:
            side = side_checked.side
    return Conditions(period=period, asset=code, side=side, not_narrowed=tuple(not_narrowed))
