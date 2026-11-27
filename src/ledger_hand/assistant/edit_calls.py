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

Given the current moment and the zone, one kind of period that is not the
user's words is let through (``this_year_read``): the user's date with
this year put to it by the model ("2026年8月3号" for "8月3号", "August 3,
2026" for "August 3"), when the year is this year in the zone, the rest is
the user's words, no sentence it is found in says a year (``YEAR_SAID``),
and the user's words read as the same days. The call is then judged again
with the user's words as its period (``EditCall.period``), and keeps the
year (``EditCall.this_year``), so that the reply can say the date was read
as this year. ``judge_edit``, ``judge_edit_at`` and ``wrong_parts`` all go
by this one judgement, so the call goes to the program, is gone on with,
and is no wrong step, alike. Any other year, or a date changed beyond the
year ("2026-8-3" for "8月3号"), is a wrong step as before. (Decided on
2026-11-27 by the session that hands out the work; the year forms are a
list, one line each, ``_year_forms``.)

``date_not_copied`` gives the date a call wrote that is not the user's
words and was not let through, for the program's sentence saying why it
was not used.

Names defined here: ``EDIT_TOOLS``, ``EditCall``, ``WrongParts``,
``ThisYear``, ``YEAR_SAID``, ``judge_edit``, ``judge_edit_at``,
``wrong_parts``, ``this_year_read`` and ``date_not_copied``.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant.judging import Accepted, Misstep, MisstepKind, judge, judge_argument
from ledger_hand.assistant.period_cuts import cut_misstep, is_cut
from ledger_hand.assistant.tools import FIELD_CHOICES, ToolName
from ledger_hand.core.time_range import Period, read_period
from ledger_hand.core.zones import zone_named
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.ports import ToolCall

EDIT_TOOLS = frozenset({ToolName.PROPOSE_TRADE_UPDATE.value, ToolName.PROPOSE_TRADE_DELETE.value})


@dataclass(frozen=True, kw_only=True)
class EditCall:
    """A call to change or delete a trade, taken: what the program goes on with.

    ``period`` and ``new_value`` are the user's words; ``asset`` is the
    model's word, not checked yet; ``side`` is a choice; ``field`` is one of
    ``FIELD_CHOICES`` for a change and ``None`` for a deletion.
    ``this_year`` is the year the model put to the user's date, let through
    as this year (``this_year_read``); ``None`` when the date was copied.
    """

    tool: ToolName
    period: str | None = None
    asset: str | None = None
    side: str | None = None
    field: str | None = None
    new_value: str | None = None
    this_year: int | None = None


@dataclass(frozen=True, kw_only=True)
class WrongParts:
    """Of a call that was a wrong step: whether its period, its new value, were wrong alone.

    ``field_taken`` says the call named a field on the list; a new value is
    only judged when it did.
    """

    period_wrong: bool
    field_taken: bool
    new_value_wrong: bool


@dataclass(frozen=True, kw_only=True)
class ThisYear:
    """A date the model wrote as the user's date with this year put to it.

    ``yours`` is the user's own words for the date, the year taken off;
    ``year`` is the year put to it. Example: "8月3号" and 2026.
    """

    yours: str
    year: int


# How a sentence says a year, anywhere in it: then a year the model put to
# its date is never let through. One more way is one more alternative.
YEAR_SAID = re.compile(
    r"今年|去年|前年|明年|后年|上一年|大前年|大后年"
    r"|[0-9０-９零〇一二两三四五六七八九十]+\s*年"
    r"|(?i:\b(?:this|last|next)\s+year\b)"
    r"|(?<![0-9])(?:19|20)[0-9]{2}(?![0-9])"
)

_CHINESE_DIGITS = "〇一二三四五六七八九"


def _year_forms(year: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The ways a year may be put before a date, and after one. Example: "2026年", ", 2026"."""
    words = "".join(_CHINESE_DIGITS[int(digit)] for digit in str(year))
    before = (
        f"{year}年",
        f"{year} 年",
        f"{year}-",
        f"{year}/",
        f"{year}.",
        f"{year % 100:02d}年",
        f"{words}年",
        f"{words.replace('〇', '零')}年",
    )
    return before, (f", {year}", f" {year}")


def this_year_read(
    period: str, user_said: Sequence[str], *, now: datetime, zone: str
) -> ThisYear | None:
    """The user's date in ``period``, when the model only put this year to it; else ``None``.

    This year is the year of ``now`` in ``zone``. The rest, once one year
    form is taken off, must be found in what the user said, no sentence it
    is found in may say a year (``YEAR_SAID``), and it must read as the
    same days as ``period``. Example, on 2026-11-27: "2026年8月3号" for
    "把8月3号那笔BTC删掉" gives "8月3号"; "2026年12月5号" gives ``None``
    (the user's "12月5号" is not read as one day yet), and so does
    "2026年8月3号" for "把去年8月3号那笔……".
    """
    year = now.astimezone(zone_named(zone)).year
    written = period.strip()
    before, after = _year_forms(year)
    rests = [written.removeprefix(form) for form in before if written.startswith(form)]
    rests += [written.removesuffix(form) for form in after if written.endswith(form)]
    theirs = read_period(written, now, zone)
    if not rests or not isinstance(theirs, Period):
        return None
    for rest in (one.strip() for one in rests):
        if not rest:
            continue
        found = [said for said in user_said if isinstance(Passage(said).find(rest), Piece)]
        if not found or any(YEAR_SAID.search(said) for said in found):
            continue
        mine = read_period(rest, now, zone)
        same = isinstance(mine, Period) and (mine.first_day, mine.last_day) == (
            theirs.first_day,
            theirs.last_day,
        )
        if same:
            return ThisYear(yours=rest, year=year)
    return None


def _period_not_copied(call: ToolCall, user_said: Sequence[str]) -> str | None:
    """The period of ``call`` when it is given as text and is not the user's words."""
    period = call.arguments.get("period")
    if call.name not in EDIT_TOOLS or not isinstance(period, str) or not period.strip():
        return None
    problem = judge_argument(ToolName(call.name), "period", call.arguments, user_said)
    if problem is None or problem.kind is not MisstepKind.NOT_COPIED:
        return None
    return period


def _let_through(
    call: ToolCall, user_said: Sequence[str], now: datetime, zone: str
) -> tuple[ToolCall, int] | None:
    """``call`` with the user's date as its period, and the year, when the model only put
    this year to the user's date."""
    period = _period_not_copied(call, user_said)
    if period is None:
        return None
    read = this_year_read(period, user_said, now=now, zone=zone)
    if read is None:
        return None
    arguments = {**call.arguments, "period": read.yours}
    return ToolCall(name=call.name, arguments=arguments), read.year


def date_not_copied(
    call: ToolCall, user_said: Sequence[str], *, now: datetime, zone: str
) -> str | None:
    """The date ``call`` wrote when it is not the user's words and was not let through.

    ``None`` when the call gives no such date: copied, cut out of a longer
    time (said another way), or let through as this year.
    """
    period = _period_not_copied(call, user_said)
    if period is None or _let_through(call, user_said, now, zone) is not None:
        return None
    return period


def judge_edit(
    call: ToolCall,
    user_said: Sequence[str],
    *,
    now: datetime | None = None,
    zone: str | None = None,
) -> EditCall | Misstep:
    """Judge a call to ``propose_trade_update`` or ``propose_trade_delete``.

    With ``now`` and ``zone``, a date the model only put this year to is let
    through, and the call judged again with the user's date in its place.
    """
    verdict = _judged(call, user_said)
    if now is None or zone is None or not isinstance(verdict, Misstep):
        return verdict
    through = _let_through(call, user_said, now, zone)
    if through is None:
        return verdict
    again = _judged(through[0], user_said)
    if isinstance(again, EditCall):
        return dataclasses.replace(again, this_year=through[1])
    return again


def _judged(call: ToolCall, user_said: Sequence[str]) -> EditCall | Misstep:
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
    verdict = judge_edit(call, user_said, now=now, zone=zone)
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
    here: it was not given. A period cut out of a longer time is wrong; one
    the model only put this year to is not (``this_year_read``), unless the
    user's words it stands for are cut out of a longer time.
    """
    tool = ToolName(call.name)
    given = call.arguments
    period = given.get("period")
    through = _let_through(call, user_said, now, zone)
    if through is not None:
        period = through[0].arguments.get("period")
    return WrongParts(
        period_wrong=_given(period)
        and (
            (through is None and judge_argument(tool, "period", given, user_said) is not None)
            or (isinstance(period, str) and is_cut(period, user_said, now, zone))
        ),
        field_taken=given.get("field") in FIELD_CHOICES,
        new_value_wrong=tool is ToolName.PROPOSE_TRADE_UPDATE
        and _given(given.get("new_value"))
        and judge_argument(tool, "new_value", given, user_said) is not None,
    )


def _given(value: object) -> bool:
    return not (value is None or (isinstance(value, str) and not value.strip()))
