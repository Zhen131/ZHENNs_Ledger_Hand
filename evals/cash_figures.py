"""Whether the model's own words say a figure no table of this turn gave, or a made-up cash figure.

The ruler of the cash balances set (``cash_balances_run``) judges with this
each reply the model wrote. Two rules (rework of 2026-11-26, after the
independent check found the first rework let made-up cash figures through
once anything was looked up):

- **Every figure is from a table or from the user.** Each number written
  with digits in the reply must be found among the figures of what the
  program or the model really had this turn: each table a read tool
  handed back (holdings, sums, trades, assets, every amount, count and
  date in them), the ledger's cash balances when they were read, and the
  numbers the user said in the chat. A figure is found when it is the
  same value, or the same value rounded to as many places as the reply
  writes (140080.18724 found as "140080.19").
- **A figure said as cash is a cash balance of that money.** In a clause
  that speaks of cash ("现金", "可用资金", "cash", or "余额"/"balance" with no
  coin, share or counting word beside it), each figure the user did not
  say must be a balance of the ledger's cash table read this turn, of the
  money the clause names (either USDT or the US dollar for a vague word);
  a figure found in the holdings does not count. In a clause that speaks
  of money put in or taken out ("入金", "出金", "充值", "提现", "deposit",
  "withdraw"), every figure the user did not say is made up: the ledger
  gives no deposits or withdrawals.

``unfound`` gives the first such figure and why, or ``None``.

Names defined here: ``unfound`` and ``figures_of``.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ledger_hand.core.cash_words import figures_in
from ledger_hand.core.ledger_records import CashBalances
from ledger_hand.core.ledger_table import VAGUE_MONEY_CODES
from ledger_hand.core.money_asks import money_named

_DIGITS = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?")
_CLAUSE = re.compile(r"[。！？!?;；\n]|\.(?![0-9])")
_CASH = re.compile(r"现金|可用资金|(?<![a-z])cash(?![a-z])")
_BALANCE = re.compile(r"余额|(?<![a-z])balances?(?![a-z])")
_COUNTERS = re.compile(r"股|个|枚|份|(?<![a-z])(?:shares?|coins?|stocks?|tokens?)(?![a-z])")
_MOVED = re.compile(
    r"入金|出金|充值|提现|取现|存入|(?<![a-z])(?:deposit|withdr)[a-z]*", re.IGNORECASE
)


def figures_of(found: object) -> set[Decimal]:
    """Every amount, count and part of a date in ``found``, however deep its shapes go."""
    values: set[Decimal] = set()
    _collect(found, values)
    return values


def _collect(found: object, values: set[Decimal]) -> None:
    if isinstance(found, bool) or found is None or isinstance(found, str):
        return
    if isinstance(found, Decimal):
        values.add(found)
    elif isinstance(found, int):
        values.add(Decimal(found))
    elif isinstance(found, datetime):
        values.update(Decimal(part) for part in (found.year, found.month, found.day))
        values.update(Decimal(part) for part in (found.hour, found.minute))
    elif isinstance(found, date):
        values.update(Decimal(part) for part in (found.year, found.month, found.day))
    elif dataclasses.is_dataclass(found) and not isinstance(found, type):
        for field in dataclasses.fields(found):
            _collect(getattr(found, field.name), values)
    elif isinstance(found, (tuple, list, set, frozenset)):
        for inner in found:
            _collect(inner, values)


def _value(written: str) -> Decimal | None:
    try:
        return Decimal(written.replace(",", ""))
    except InvalidOperation:
        return None


def _matches(written: str, value: Decimal, among: Iterable[Decimal]) -> bool:
    places = len(written.split(".")[1]) if "." in written else 0
    for one in among:
        if one == value:
            return True
        if places and one.is_finite() and one.quantize(Decimal(1).scaleb(-places)) == value:
            return True
    return False


def _said_by_user(user_said: Sequence[str]) -> set[Decimal]:
    return {value for text in user_said for _, value in figures_in(text)}


def _speaks_of_cash(clause: str, held: Sequence[str]) -> bool:
    if _CASH.search(clause):
        return True
    if not _BALANCE.search(clause):
        return False
    if _COUNTERS.search(clause):
        return False
    return not any(name.casefold() in clause for name in held if name.strip())


def _cash_rows(clause: str, cash: CashBalances | None) -> list[Decimal]:
    """The balances a figure said as cash in ``clause`` may be: of the money it names."""
    if cash is None:
        return []
    codes = {row.code for row in cash.balances}
    named = money_named(clause, [(code, code) for code in codes])
    wanted: set[str] = set()
    for code in named:
        wanted |= set(VAGUE_MONEY_CODES) if code == "vague" else {code}
    return [row.balance for row in cash.balances if not wanted or row.code in wanted]


def unfound(
    reply: str,
    *,
    tables: Iterable[object],
    cash: CashBalances | None,
    user_said: Sequence[str],
    held: Sequence[str] = (),
) -> str | None:
    """The first figure of ``reply`` no table or user gave, or said as cash or money moved
    that is no cash balance of its money, and why; ``None`` when there is none.

    ``tables`` are what the read tools handed back this turn; ``cash`` the
    ledger's cash balances when they were read; ``held`` the names of the
    coins and shares, so that "BTC 余额" is no cash.
    """
    heard = _said_by_user(user_said)
    known = figures_of(tuple(tables)) | figures_of(cash)
    for clause in (part.casefold() for part in _CLAUSE.split(reply)):
        for match in _DIGITS.finditer(clause):
            written = match.group(0)
            value = _value(written)
            if value is None or value in heard:
                continue
            if _MOVED.search(clause):
                return (
                    f"{written!r} said as money put in or taken out, which the ledger never gives"
                )
            if _speaks_of_cash(clause, held):
                if not _matches(written, value, _cash_rows(clause, cash)):
                    return f"{written!r} said as cash, and no cash balance of that money"
                continue
            if not _matches(written, value, known):
                return f"{written!r} is in no table of this turn"
    return None
