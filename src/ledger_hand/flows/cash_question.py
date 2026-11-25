"""A question about cash, caught before the model is asked, and answered truthfully.

The assistant cannot look up a cash balance, a deposit or a withdrawal:
none of the eight tools it hands the model reads one. Asked "我还有多少USDT",
the model may say a figure of its own, or take a holding's cost or the
money spent in a stretch of time for what is left. So the program reads
what the user said first (``core.cash_words``):

- ``caught`` says whether it asks about cash. The words for a money are
  the base words and, only when the sentence has the shape of asking what
  is still had or names a balance, the code and name of each cash asset
  the ledger lists (``list_assets``, asked for then and only then); the
  names of its other assets keep "ETH 余额" a holding. When the ledger
  cannot be asked, the base words and the built-in coins' names are used.
- ``CASH_WORDS`` is what the user is told then, in place of anything the
  model would say: this assistant cannot look up cash yet, the ledger's
  home page shows the cash balance, and no figure is worked out from the
  trades. No table is laid out and no figure is said.
- ``withheld_cash`` is the check behind it: when the question was not
  caught, and the model answered without looking anything up, words with
  a number beside a money that the user never said in this chat ("50
  USDT", "$50", "5U") are not shown; the user is told ``CASH_WORDS``
  instead. A figure the user said may be asked back.

What the user is told is the program's own, never the model's. (The
product owner, 2026-11-25: "账本现在没有查现金余额的工具。助手被问到现金就照实说
查不到，不要自己从买卖里推。")

Names defined here: ``CASH_WORDS``, ``caught`` and ``withheld_cash``.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from ledger_hand.assistant.explanation import Withheld, numbers_in
from ledger_hand.core.cash_words import (
    BASE_MONEY_WORDS,
    CashAsk,
    cash_question,
    figures_beside_money,
    held_names,
    may_ask_what_is_left,
    money_words,
    names_a_balance,
)
from ledger_hand.core.ledger_records import Asset
from ledger_hand.core.ledger_table import names_of
from ledger_hand.ports import LedgerError, LedgerPort

CASH_WORDS = (
    "This assistant cannot look up cash yet: it has no way to read a cash balance, "
    "a deposit or a withdrawal, so I cannot tell you this, and I will not work a figure "
    "out from your trades. Your cash balance is on the ledger's home page. You can ask "
    "me about what you hold, your trades, or the sums of a stretch of time."
)


def _assets(ledger: LedgerPort) -> tuple[Asset, ...] | None:
    """The ledger's list of assets, or ``None`` when it cannot be asked."""
    try:
        return ledger.list_assets()
    except LedgerError:
        return None


def _words(ledger: LedgerPort) -> tuple[str, ...]:
    """The words for a money, the ledger's cash assets among them when it can be asked."""
    assets = _assets(ledger)
    return money_words(assets) if assets is not None else BASE_MONEY_WORDS


def caught(said: str, ledger: LedgerPort) -> CashAsk | None:
    """Which kind of question about cash ``said`` is, or ``None`` when it goes to the model.

    The ledger's assets are asked for only when the sentence names a balance
    or has the shape of asking what is still had. When it cannot be asked,
    the base words for a money and the built-in coins' names are used.
    """
    if not (may_ask_what_is_left(said) or names_a_balance(said)):
        return cash_question(said)
    assets = _assets(ledger)
    if assets is None:
        built_in = tuple(name for name, _ in names_of(()).built_in)
        return cash_question(said, BASE_MONEY_WORDS, built_in)
    return cash_question(said, money_words(assets), held_names(assets))


def _said_before(number: str, user_said: Sequence[str]) -> bool:
    """Whether the user wrote ``number`` in what they said: the same value, or the same words."""
    try:
        value = Decimal(number.replace(",", ""))
    except InvalidOperation:
        return any(number in text for text in user_said)
    for text in user_said:
        for written in numbers_in(text):
            try:
                if Decimal(written.replace(",", "")) == value:
                    return True
            except InvalidOperation:
                continue
    return False


def withheld_cash(reply: str, ledger: LedgerPort, user_said: Sequence[str] = ()) -> Withheld | None:
    """Why the model's ``reply``, with nothing looked up, may not be shown; ``None`` when it may.

    Only a number beside a money that the user never said in this chat
    counts: a figure the user said, asked back or said again ("手续费是 1 USDT
    吗？" after "手续费 1 USDT"), is let through. (2026-11-25, the first
    rework: such questions were turned away before.) The ledger is asked
    for its cash assets only when the reply holds a digit.
    """
    found = figures_beside_money(reply)
    if any(character.isdigit() for character in reply):
        found = figures_beside_money(reply, _words(ledger))
    made_up = [words for words, number in found if not _said_before(number, user_said)]
    if not made_up:
        return None
    return Withheld(f"{made_up[0]!r} is a figure beside a money the user never said")
