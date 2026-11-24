"""Judging a call to change or delete a trade: what the program takes from it, or what is wrong.

The model names the trade to change or delete by the same three arguments
as a list of trades (``period``, ``asset``, ``side``), and, for a change,
which part (``field``, a choice) and the new value (``new_value``, copied).
``judge_edit`` judges such a call the way any call is judged
(``judging``), with two arguments taken out first:

- ``trade``, the words the user picked a listed trade with, is dropped
  unread, given or not, text or not, and is no wrong step. The program
  never takes a trade the model names: the trade to change is the only
  one found, or the one whose number the user gives when the program asks.
- ``asset`` is kept apart, as for the read tools, and checked later against
  what the user said (``narrowing``). An asset that is not text is left in,
  so that it is still a wrong step.

So a period the model wrote itself ("2023-09-25" for "9月25号") is a wrong
step, as for the read tools, and so is a new value that is not the user's
words.

``wrong_parts`` says, for a call that was a wrong step, whether its period
and its new value each were wrong on their own: when the model goes wrong
twice in a row and its second try is such a call, the program tells the
user which of the two it could not take (``flows.editing``).

``judge_edit_at`` judges the same way, and also takes a period cut out of
a longer time the user said for a wrong step (``period_cuts``); it is the
one the program goes by.

Names defined here: ``EDIT_TOOLS``, ``EditCall``, ``WrongParts``,
``judge_edit``, ``judge_edit_at`` and ``wrong_parts``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant.judging import Accepted, Misstep, judge, judge_argument
from ledger_hand.assistant.period_cuts import cut_misstep, is_cut
from ledger_hand.assistant.tools import FIELD_CHOICES, ToolName
from ledger_hand.ports import ToolCall

EDIT_TOOLS = frozenset({ToolName.PROPOSE_TRADE_UPDATE.value, ToolName.PROPOSE_TRADE_DELETE.value})


@dataclass(frozen=True, kw_only=True)
class EditCall:
    """A call to change or delete a trade, taken: what the program goes on with.

    ``period`` and ``new_value`` are the user's words; ``asset`` is the
    model's word, not checked yet; ``side`` is a choice; ``field`` is one of
    ``FIELD_CHOICES`` for a change and ``None`` for a deletion.
    """

    tool: ToolName
    period: str | None = None
    asset: str | None = None
    side: str | None = None
    field: str | None = None
    new_value: str | None = None


@dataclass(frozen=True, kw_only=True)
class WrongParts:
    """Of a call that was a wrong step: whether its period, its new value, were wrong alone.

    ``field_taken`` says the call named a field on the list; a new value is
    only judged when it did.
    """

    period_wrong: bool
    field_taken: bool
    new_value_wrong: bool


def judge_edit(call: ToolCall, user_said: Sequence[str]) -> EditCall | Misstep:
    """Judge a call to ``propose_trade_update`` or ``propose_trade_delete``."""
    if call.name not in EDIT_TOOLS:
        raise ValueError(f"{call.name!r} neither changes nor deletes a trade")
    arguments = {name: value for name, value in call.arguments.items() if name != "trade"}
    asset = arguments.get("asset")
    if isinstance(asset, str):
        del arguments["asset"]
    verdict = judge(ToolCall(name=call.name, arguments=arguments), user_said)
    if isinstance(verdict, Misstep):
        return verdict
    return _taken(verdict, asset if isinstance(asset, str) and asset.strip() else None)


def judge_edit_at(
    call: ToolCall, user_said: Sequence[str], *, now: datetime, zone: str
) -> EditCall | Misstep:
    """``judge_edit``, with a period cut out of a longer time the user said a wrong step too."""
    verdict = judge_edit(call, user_said)
    period = verdict.period if isinstance(verdict, EditCall) else None
    if period is not None and is_cut(period, user_said, now, zone):
        return cut_misstep(period)
    return verdict


def _taken(accepted: Accepted, asset: str | None) -> EditCall:
    given = accepted.arguments
    return EditCall(
        tool=accepted.tool,
        period=given.get("period"),
        asset=asset,
        side=given.get("side"),
        field=given.get("field"),
        new_value=given.get("new_value"),
    )


def wrong_parts(
    call: ToolCall, user_said: Sequence[str], *, now: datetime, zone: str
) -> WrongParts:
    """Whether the period, and the new value, of ``call`` are each wrong on their own.

    A period or a new value left out, or given as blank text, is not wrong
    here: it was not given. A period cut out of a longer time is wrong.
    """
    tool = ToolName(call.name)
    given = call.arguments
    period = given.get("period")
    return WrongParts(
        period_wrong=_given(period)
        and (
            judge_argument(tool, "period", given, user_said) is not None
            or (isinstance(period, str) and is_cut(period, user_said, now, zone))
        ),
        field_taken=given.get("field") in FIELD_CHOICES,
        new_value_wrong=tool is ToolName.PROPOSE_TRADE_UPDATE
        and _given(given.get("new_value"))
        and judge_argument(tool, "new_value", given, user_said) is not None,
    )


def _given(value: object) -> bool:
    return not (value is None or (isinstance(value, str) and not value.strip()))
