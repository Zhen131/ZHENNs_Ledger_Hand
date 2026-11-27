"""The program's own words when it changes or deletes a trade, with the tables it shows.

None of these words is written by the model, and every figure in them is
the ledger's, the user's, or worked out by the program. Each function gives
the whole reply for one ending: a fixed English sentence, and the lines of
a table under it, one line each.

- ``picking_words``: more than one trade matches; the list, numbered from 1
  in time order, under the conditions it was found by, and the question.
- ``too_many_words``: more match than are listed; the latest, and a request
  to say more.
- ``choosing_words``: a new amount leaves the three out of step; the ways
  to put them back, numbered, and the question.
- ``sent_words``: a proposal waits in the ledger: for a change, the trade
  before and after, side by side, the parts that change marked; for a
  deletion, the trade.
- ``not_found_words``: nothing matches, and what was looked for.
- ``date_not_as_said_words``: a date the model wrote is not the user's
  words: what it wrote, what the user said, and an example to say instead.
- ``this_year_line``: the line added when the user's date was looked for
  read as this year, the model having put this year to it.
- the fixed sentences for the rest.

Names defined here: ``NO_CONDITIONS``, ``CANCELLED``, ``NOTHING_TO_CHANGE``,
``GONE``, ``MAYBE_SENT``, ``PERIOD_AGAIN``, ``THIS_YEAR_WORDS``,
``DATE_NOT_AS_SAID``, ``VALUE_AGAIN``, ``picking_words``,
``too_many_words``, ``choosing_words``, ``sent_words``, ``not_found_words``,
``refused_words``, ``failed_words``, ``date_not_as_said_words``,
``this_year_line`` and ``not_done_words``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from ledger_hand.assistant.lookups import Conditions, conditions_lines, trade_row, when_text
from ledger_hand.assistant.new_values import FIELD_WORDS, Fixes
from ledger_hand.core.chinese import CHINESE_CHARACTER
from ledger_hand.core.ledger_records import LedgerTrade, TradeFacts
from ledger_hand.core.time_range import Period, read_period
from ledger_hand.core.trade import Amount
from ledger_hand.core.zones import zone_named
from ledger_hand.extraction.passage import Passage, Piece

NO_CONDITIONS = (
    "Please say which trade you mean: the day it was on, and the asset, such as "
    "'10月6号那笔BTC'. Nothing was proposed."
)
CANCELLED = "Cancelled: nothing was proposed."
NOTHING_TO_CHANGE = "The trade already has that value, so there is nothing to change."
GONE = (
    "That trade is no longer in the ledger as it was listed, so nothing was proposed. "
    "Please say again which trade you mean."
)
# The ledger's own rule 4 (assistant-link/README.md): a proposal it did not
# answer in time may still have reached it, so it is never sent again.
MAYBE_SENT = (
    "The ledger did not answer in time, so this may already be waiting there. Nothing "
    "was sent again. Please look at the ledger's pending list first."
)
PERIOD_AGAIN = (
    "I could not tell which day's trade you mean, so nothing was proposed. "
    "Please say it again with the date, such as '9月25号那笔ADA'."
)
# Added to the reply when the user's date was looked for read as this year,
# the model having put this year to it (2026-11-27). "read as this year" is
# the word to look for.
THIS_YEAR_WORDS = "The date was read as this year ({year})."
# Said when a date the model wrote is not the user's words and was not let
# through (2026-11-27). "Dates are taken only as you said them" is the word
# to look for.
DATE_NOT_AS_SAID = (
    'I could not use the date: the assistant wrote "{written}", but you said "{yours}". '
    "Dates are taken only as you said them. Please say it again with the date as you "
    'mean it, such as "{example}".'
)
# A year at the start or the end of a date, any year: what is left is looked
# for in the user's words.
_ANY_YEAR = re.compile(
    r"^\s*(?:[0-9]{4}\s*年|[0-9]{2}年|[〇零一二三四五六七八九]{4}年|[0-9]{4}[-/.])"
    r"|,?\s*[0-9]{4}\s*$"
)
_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
# How many years back an example date is looked for: far enough for 29 February.
_YEARS_BACK = 8
VALUE_AGAIN = (
    "I could not tell what you want it changed to, so nothing was proposed. "
    "Please say again what the new value is, as you would write it."
)
_PICK_QUESTION = (
    "Which one do you mean? Answer with its number, such as '2' or '第二笔', or say 'cancel'."
)


def _n(value: Decimal) -> str:
    return format(value, "f")


def _found_by(conditions: Conditions) -> list[str]:
    return ["Found by:", *(f"  {line}" for line in conditions_lines(conditions))]


def _numbered(trades: Sequence[LedgerTrade]) -> list[str]:
    return [f"  {number}. {trade_row(trade)}" for number, trade in enumerate(trades, start=1)]


def picking_words(conditions: Conditions, trades: Sequence[LedgerTrade], why: str = "") -> str:
    """More than one trade matches: the numbered list, and which one, asked."""
    lines = [*([why] if why else []), f"{len(trades)} trades match:"]
    lines += _found_by(conditions)
    lines += _numbered(trades)
    lines.append(_PICK_QUESTION)
    return "\n".join(lines)


def too_many_words(conditions: Conditions, count: int, latest: Sequence[LedgerTrade]) -> str:
    """More match than are listed: the latest, and a request to say more. Nothing waits."""
    lines = [f"{count} trades match; these are the latest {len(latest)}:"]
    lines += _found_by(conditions)
    lines += [f"  {trade_row(trade)}" for trade in latest]
    lines.append(
        "That is too many to choose from. Please say more about which trade you mean: "
        "the day, the asset, or buy or sell. Nothing was proposed."
    )
    return "\n".join(lines)


_AMOUNT_WORDS = {Amount.QUANTITY: "quantity", Amount.PRICE: "price", Amount.TOTAL: "total"}


def choosing_words(trade: LedgerTrade, fixes: Fixes, why: str = "") -> str:
    """A new amount leaves the three out of step: the ways to put them back, and which."""
    facts = trade.facts
    changed = _AMOUNT_WORDS[fixes.changed]
    lines = [*([why] if why else [])]
    lines.append(
        f"With only the {changed} changed, quantity times price no longer matches the total. "
        "Which should change with it?"
    )
    lines.append(f"  The trade: {trade_row(trade)}")
    for number, fix in enumerate(fixes.fixes, start=1):
        follows = _AMOUNT_WORDS[fix.follows]
        new = {Amount.QUANTITY: fix.quantity, Amount.PRICE: fix.price, Amount.TOTAL: fix.total}
        unit = facts.asset if fix.follows is Amount.QUANTITY else facts.quote
        lines.append(
            f"  {number}. the {follows} becomes {_n(new[fix.follows])} {unit} "
            f"(quantity {_n(fix.quantity)} {facts.asset}, price {_n(fix.price)} {facts.quote}, "
            f"total {_n(fix.total)} {facts.quote})"
        )
    names = " or ".join(f"'{_AMOUNT_WORDS[fix.follows]}'" for fix in fixes.fixes)
    numbers = " or ".join(str(number) for number in range(1, len(fixes.fixes) + 1))
    lines.append(f"Answer {numbers}, or {names}, or say 'cancel'.")
    return "\n".join(lines)


def _parts(facts: TradeFacts) -> list[tuple[str, str]]:
    return [
        ("time", when_text(facts)),
        ("side", facts.side.value),
        ("asset", facts.asset),
        ("quantity", _n(facts.quantity)),
        ("price", f"{_n(facts.price)} {facts.quote}"),
        ("total", f"{_n(facts.total)} {facts.quote}"),
        ("fee", f"{_n(facts.fee)} {facts.fee_asset}"),
        ("platform", facts.platform or "-"),
        ("note", facts.note or "-"),
    ]


def sent_words(
    proposal: str, conditions: Conditions, before: LedgerTrade, after: TradeFacts | None
) -> str:
    """A proposal waits in the ledger: the change side by side, or the trade to delete."""
    if after is None:
        lines = [
            f"I asked the ledger to delete this trade. It waits there as {proposal} until "
            "you confirm it; nothing is deleted before that.",
            f"  {trade_row(before)}",
        ]
    else:
        lines = [
            f"I asked the ledger to change this trade. It waits there as {proposal} until "
            "you confirm it; nothing changes before that.",
            "  part | before | after",
        ]
        for (name, was), (_, now) in zip(_parts(before.facts), _parts(after), strict=True):
            mark = "  <- changed" if was != now else ""
            lines.append(f"  {name} | {was} | {now}{mark}")
    return "\n".join([*lines, *_found_by(conditions)])


def not_found_words(conditions: Conditions) -> str:
    """Nothing matches: say so, and what was looked for. Nothing is looked for more widely."""
    return "\n".join(["No trade matches, so nothing was proposed.", *_found_by(conditions)])


def refused_words(message: str) -> str:
    """The ledger's check turned the proposal down: its reason, and that nothing waits."""
    return f"The ledger turned this down, so nothing waits to be confirmed: {message}"


def failed_words(message: str) -> str:
    """The ledger could not be asked."""
    return f"The ledger could not be asked, so nothing was proposed: {message}"


def date_not_as_said_words(
    written: str, user_said: Sequence[str], said: str, *, now: datetime, zone: str
) -> str:
    """Why a date the model wrote was not used: what it wrote, what the user said, an example.

    ``said`` is the user's last sentence as said; it stands for the user's
    words when the date, its year taken off, is not found in what they said.
    The example is the user's date with the latest year it has already come
    in, never a day ahead; with none, today. Example, on 2026-11-27: "2025年
    8月3号" for "8月3号" gives the example "2026年8月3号"; "12月5号" gives
    "2025年12月5号".
    """
    rest = _ANY_YEAR.sub("", written, count=1).strip()
    found = bool(rest) and any(isinstance(Passage(one).find(rest), Piece) for one in user_said)
    yours = rest if found else said
    return DATE_NOT_AS_SAID.format(
        written=written, yours=yours, example=_example(rest if found else "", now, zone)
    )


def _example(yours: str, now: datetime, zone: str) -> str:
    """The user's date with the latest year it has already come in, or today's date."""
    today = now.astimezone(zone_named(zone)).date()
    chinese = CHINESE_CHARACTER.search(yours) is not None
    for year in range(today.year, today.year - _YEARS_BACK, -1):
        if not yours:
            break
        written = f"{year}年{yours}" if chinese else f"{yours}, {year}"
        read = read_period(written, now, zone)
        if isinstance(read, Period) and read.last_day <= today:
            return written
    if chinese or not yours or not yours.isascii():
        return f"{today.year}年{today.month}月{today.day}号"
    return f"{_MONTHS[today.month - 1]} {today.day}, {today.year}"


def this_year_line(year: int) -> str:
    """The line added once the user's date, read as this year, was looked for."""
    return THIS_YEAR_WORDS.format(year=year)


def not_done_words(left: Sequence[tuple[str, str | None, str | None]]) -> str:
    """What else was asked in the same step and not done: one change or deletion at a time.

    ``left`` holds, for each change or deletion not done, the tool's name,
    the field and the new value.
    """
    parts = []
    for tool, field, value in left:
        if tool == "propose_trade_delete":
            parts.append("deleting a trade")
        else:
            what = FIELD_WORDS.get(field or "", "a part")
            parts.append(f"changing the {what}" + (f" to {value!r}" if value else ""))
    return (
        f"I do one change or deletion at a time, so this was not done: {'; '.join(parts)}. "
        "Please say it again once this one is settled."
    )
