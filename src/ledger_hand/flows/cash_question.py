"""A question about cash, caught before the model is asked, and answered truthfully.

The assistant cannot look up a cash balance, a deposit or a withdrawal:
none of the eight tools it hands the model reads one. Asked "我还有多少USDT",
the model may say a figure of its own, or take a holding's cost or the
money spent in a stretch of time for what is left. So the program reads
what the user said first (``core.cash_words``):

- ``caught`` says whether it asks about cash. The words for a money are
  the base words and, only when the sentence has the shape of asking what
  is still had, the code and name of each cash asset the ledger lists
  (``list_assets``, asked for then and only then). When the ledger cannot
  be asked, the base words are used.
- ``CASH_WORDS`` is what the user is told then, in place of anything the
  model would say: this assistant cannot look up cash yet, the ledger's
  home page shows the cash balance, and no figure is worked out from the
  trades. No table is laid out and no figure is said.
- ``withheld_cash`` is the check behind it: when the question was not
  caught, and the model answered without looking anything up, words with
  a number beside a money ("50 USDT", "$50", "5U") are not shown; the
  user is told ``CASH_WORDS`` instead.

What the user is told is the program's own, never the model's. (The
product owner, 2026-11-25: "账本现在没有查现金余额的工具。助手被问到现金就照实说
查不到，不要自己从买卖里推。")

Names defined here: ``CASH_WORDS``, ``caught`` and ``withheld_cash``.
"""

from __future__ import annotations

from ledger_hand.assistant.explanation import Withheld
from ledger_hand.core.cash_words import (
    BASE_MONEY_WORDS,
    CashAsk,
    cash_question,
    figure_beside_money,
    may_ask_what_is_left,
    money_words,
)
from ledger_hand.ports import LedgerError, LedgerPort

CASH_WORDS = (
    "This assistant cannot look up cash yet: it has no way to read a cash balance, "
    "a deposit or a withdrawal, so I cannot tell you this, and I will not work a figure "
    "out from your trades. Your cash balance is on the ledger's home page. You can ask "
    "me about what you hold, your trades, or the sums of a stretch of time."
)


def _words(ledger: LedgerPort) -> tuple[str, ...]:
    """The words for a money, the ledger's cash assets among them when it can be asked."""
    try:
        return money_words(ledger.list_assets())
    except LedgerError:
        return BASE_MONEY_WORDS


def caught(said: str, ledger: LedgerPort) -> CashAsk | None:
    """Which kind of question about cash ``said`` is, or ``None`` when it goes to the model."""
    words = _words(ledger) if may_ask_what_is_left(said) else BASE_MONEY_WORDS
    return cash_question(said, words)


def withheld_cash(reply: str, ledger: LedgerPort) -> Withheld | None:
    """Why the model's ``reply``, with nothing looked up, may not be shown; ``None`` when it may.

    The ledger is asked for its cash assets only when the base words find
    nothing and the reply holds a digit.
    """
    found = figure_beside_money(reply)
    if found is None and any(character.isdigit() for character in reply):
        found = figure_beside_money(reply, _words(ledger))
    if found is None:
        return None
    return Withheld(f"{found!r} is a figure beside a money, and nothing was looked up")
