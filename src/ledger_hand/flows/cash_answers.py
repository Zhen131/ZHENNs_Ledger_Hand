"""The ledger's cash balances answered, and money the assistant does not record said truthfully.

Three readings of what the user said come before the model is asked
(``conversation``), in this order (decided on 2026-11-26):

1. Money moved that the assistant does not record (``money_asks.statement``):
   a deposit, a withdrawal, an exchange of moneys or a dividend, said, not
   asked. Alone, the program says ``manual_words`` and sends nothing; with
   a buy or a sell beside it, the trade is recorded as before and the
   reply ends with ``manual_tail``: never half of it done unsaid.
2. The question about cash (``cash_question.caught``), unchanged.
3. Only when that one finds none: how much of any money of the tables is
   still had (``money_asks.left_asked``), "我还有多少欧元" among them.

``look_up`` asks the ledger for its cash balances, once, and says what it
found (``CashSeen``): the balances, that the ledger has no tool for them
(an older one, ``NO_CASH_TOOL``), or that it could not be asked.
``cash_words`` is what the user is told of a question about cash then:

- the ledger has the tool, and a balance or a "how much is left" was
  asked: ``BALANCES_WORDS`` with the day, and the table of every money, 0
  among them, as the ledger gave it, laid out by the page. Nothing is added
  up and nothing converted. A money named that the ledger lacks gets
  ``not_in_ledger_words``; a balance below 0 gets ``BELOW_ZERO_WORDS``; a
  vague word ("美金") picks no row. No row at all: ``NO_CASH_ROWS``.
- a deposit or a withdrawal asked: ``NO_DETAIL_WORDS``, no table, since
  a balance is not a sum of deposits.
- the ledger has no tool: ``CASH_WORDS``, word for word as before.
- the ledger could not be asked: ``not_asked_words``, no figure.

``WITHHELD_WORDS`` stand in for the model's words with a figure beside a
money unasked (``cash_question.withheld_cash``) when the ledger has the
tool: ``CASH_WORDS`` would no longer be true then.

Every word here is the program's; no figure passes through the model.

Names defined here: ``CashSeen``, ``look_up``, ``cash_words``,
``BALANCES_WORDS``, ``NO_CASH_ROWS``, ``BELOW_ZERO_WORDS``,
``NO_DETAIL_WORDS``, ``WITHHELD_WORDS``, ``not_in_ledger_words``,
``not_asked_words``, ``manual_words``, ``manual_tail``, ``NOT_RECORDED_EITHER``
and ``money_of_the_ledger``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ledger_hand.core.cash_words import CashAsk
from ledger_hand.core.ledger_records import NO_CASH_TOOL, Asset, AssetKind, CashBalances
from ledger_hand.core.money_asks import Manual
from ledger_hand.flows.cash_question import CASH_WORDS
from ledger_hand.ports import LedgerError, LedgerPort

BALANCES_WORDS = (
    "These are the cash balances in the ledger, counted up to {day}. Each money is "
    "counted on its own: they are not added together and not converted."
)
NO_CASH_ROWS = "The ledger holds no cash money at all."
BELOW_ZERO_WORDS = (
    "A balance below zero means the ledger records more of that money going out than "
    "coming in, most likely a deposit that was never recorded; it is not a debt."
)
NO_DETAIL_WORDS = (
    "The ledger hands the assistant only each money's balance, not the deposits or "
    "withdrawals one by one, so I cannot tell you this. Ask how much of a money you "
    'still have, such as "how much USDT do I have", to see the cash balances.'
)
WITHHELD_WORDS = (
    "I do not say a cash figure that was not read from the ledger. Ask how much of a "
    'money you still have, such as "how much USDT do I have", to see the ledger\'s '
    "cash balances."
)
NOT_RECORDED_EITHER = (
    "The trade you spoke of was not recorded either: please say it again on its own."
)


@dataclass(frozen=True)
class CashSeen:
    """What the ledger said of its cash this time, asked once.

    ``tool`` is whether it has a tool for cash balances: ``None`` when it
    could not be asked (``failure`` says why). ``balances`` are its own,
    when it gave them. ``named`` is the money the user named, by code, when
    one was. ``shown`` says the balances were laid out as the answer.
    """

    tool: bool | None
    balances: CashBalances | None = None
    failure: LedgerError | None = None
    named: str | None = None
    shown: bool = False


def look_up(ledger: LedgerPort) -> CashSeen:
    """The ledger asked for its cash balances once: them, no tool, or why it could not be."""
    try:
        return CashSeen(tool=True, balances=ledger.cash_balances())
    except LedgerError as error:
        if error.code == NO_CASH_TOOL:
            return CashSeen(tool=False)
        return CashSeen(tool=None, failure=error)


def money_of_the_ledger(assets: Sequence[Asset]) -> tuple[tuple[str, str], ...]:
    """The code and name of each cash asset of the ledger, each with its code."""
    return tuple(
        (word, asset.code)
        for asset in assets
        if asset.kind is AssetKind.CASH
        for word in (asset.code, asset.name)
    )


def not_in_ledger_words(code: str) -> str:
    """The ledger has no money ``code``: for example, "The ledger has no money EUR."."""
    return f"The ledger has no money {code}."


def not_asked_words(failure: LedgerError) -> str:
    """The ledger could not be asked for its cash balances, and why; no figure."""
    return (
        f"The ledger could not be asked for its cash balances: {failure.message} "
        "No figure is given, and none is worked out from your trades."
    )


def cash_words(asked: CashAsk, seen: CashSeen) -> tuple[str, CashSeen]:
    """What the user is told of the question ``asked``, and ``seen`` as laid out (``shown``)."""
    if seen.tool is False:
        return CASH_WORDS, seen
    if seen.failure is not None:
        return not_asked_words(seen.failure), seen
    if asked in (CashAsk.DEPOSIT, CashAsk.WITHDRAWAL):
        return NO_DETAIL_WORDS, seen
    balances = seen.balances
    assert balances is not None
    lines: list[str] = []
    if balances.balances:
        lines.append(BALANCES_WORDS.format(day=balances.day.isoformat()))
    else:
        lines.append(NO_CASH_ROWS)
    codes = {row.code for row in balances.balances}
    if seen.named is not None and seen.named not in codes:
        lines.append(not_in_ledger_words(seen.named))
    if any(row.balance < 0 for row in balances.balances):
        lines.append(BELOW_ZERO_WORDS)
    shown = CashSeen(tool=True, balances=balances, named=seen.named, shown=bool(balances.balances))
    return "\n".join(lines), shown


def _kinds(kinds: Sequence[Manual]) -> str:
    names = [kind.value for kind in kinds]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def manual_words(kinds: Sequence[Manual]) -> str:
    """Money moved that the assistant does not record, said alone: nothing was sent.

    For example: "The assistant does not record deposits, so nothing was
    sent to the ledger. Please record it in the ledger yourself."
    """
    return (
        f"The assistant does not record {_kinds(kinds)}, so nothing was sent to the "
        "ledger. Please record it in the ledger yourself."
    )


def manual_tail(kinds: Sequence[Manual]) -> str:
    """The line that ends a reply to a trade said beside money the assistant does not record."""
    return (
        f"You also spoke of {_kinds(kinds)}: the assistant does not record those. "
        "Please record that part in the ledger yourself."
    )
