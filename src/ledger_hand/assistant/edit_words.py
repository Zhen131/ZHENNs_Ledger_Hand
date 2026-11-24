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
- the fixed sentences for the rest.

Names defined here: ``NO_CONDITIONS``, ``CANCELLED``, ``NOTHING_TO_CHANGE``,
``GONE``, ``PERIOD_AGAIN``, ``VALUE_AGAIN``, ``picking_words``,
``too_many_words``, ``choosing_words``, ``sent_words``, ``not_found_words``,
``refused_words``, ``failed_words`` and ``not_done_words``.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ledger_hand.assistant.lookups import Conditions, conditions_lines, trade_row
from ledger_hand.assistant.new_values import FIELD_WORDS, Fixes
from ledger_hand.core.ledger_records import LedgerTrade, TradeFacts
from ledger_hand.core.trade import Amount

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
PERIOD_AGAIN = (
    "I could not tell which day's trade you mean, so nothing was proposed. "
    "Please say it again with the date, such as '9月25号那笔ADA'."
)
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
        ("time", facts.occurred.strftime("%Y-%m-%d %H:%M")),
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
