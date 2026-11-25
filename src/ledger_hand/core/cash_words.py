"""The words that tell a question about cash, and a figure said beside a money.

This module tells, from the user's own words alone, whether they ask about
cash. It asks no ledger and no model. None of the eight tools the
assistant uses reads a cash balance, a deposit or a withdrawal, so such a
question is answered by the program itself, truthfully
(``flows.cash_question``).

What a question about cash is (``CashAsk``), one kind each:

- ``CASH``: cash or a balance named outright: "现金", "余额", "可用资金",
  "cash", "balance", "buying power". "balance" is a word of its own:
  "rebalance" and "balanced" are not it. A balance attached to an asset
  that is not cash ("ETH 余额", "BTC balance", "balance of ETH", the names
  handed in as ``held``) is a holding, not cash (first rework, 2026-11-25).
- ``LEFT``: how much of a money is still had: "我还有多少USDT",
  "账上还剩多少美元", "USDT还剩多少", "how much USD do I have left",
  "do I still have any USDT". The money is one of ``money_words``: the
  nicknames of ``ledger_table.MONEY_NICKNAMES``, "钱", "money", and the
  code and name of each asset the ledger lists as cash. No money is
  written in here for good: what the ledger calls cash is handed in.
- ``DEPOSIT``: money put in: "入金", "入了多少金", "充值", "存入",
  "deposit", "top up". "买入金额", "收入金额" are not it.
- ``WITHDRAWAL``: money taken out: "出金", "出了多少金", "提现", "取现",
  "withdraw". "卖出金额", "支出金额" are not it.

What it does not catch (``docs/known-gaps.md``): a question that names no
money and none of these words ("我还能买多少BTC", "how much do I have left"),
or that names a coin rather than a money ("我还有多少BTC" is a holding, and
goes to the model as before).

``figure_beside_money`` finds a number written right beside a money word
("50 USDT", "$50", "50美元", "5U", "五十美元"): the check made of the model's
words when nothing was looked up, so that no figure the model made up is
ever said as cash.

Why the words are in one place: catching the question and the check of
the model's words must use the same list, or one would know a money the
other does not. (The product owner, 2026-11-25: asked about cash, say
truthfully that it cannot be looked up.)

Names defined here: ``CashAsk``, ``BASE_MONEY_WORDS``, ``money_words``,
``held_names``, ``names_a_balance``, ``may_ask_what_is_left``,
``cash_question``, ``figures_beside_money`` and ``figure_beside_money``.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from collections.abc import Iterable, Sequence

from ledger_hand.core.ledger_records import Asset, AssetKind
from ledger_hand.core.ledger_table import MONEY_NICKNAMES, names_of


class CashAsk(enum.Enum):
    """Which kind of question about cash was said."""

    CASH = "cash or a balance"
    LEFT = "how much of a money is still had"
    DEPOSIT = "money put in"
    WITHDRAWAL = "money taken out"


# Words for a money whatever the ledger lists as cash.
BASE_MONEY_WORDS: tuple[str, ...] = (
    *(word for word, _ in MONEY_NICKNAMES),
    "钱",
    "money",
    "cash",
)

_CASH = (
    r"现金",
    r"可用资金",
    r"(?<![a-z])cash(?![a-z])",
    r"(?<![a-z])buying power(?![a-z])",
)
# "余额" and "balance" are cash only when no asset that is not cash is attached to them.
_BALANCE = r"(?:余额|(?<![a-z])balances?(?![a-z]))"
_DEPOSIT = (
    r"(?<![收投买录输转加])入金(?!额)",
    r"入了[^，,。.?？!！]{0,3}?金(?!额)",
    r"充值",
    r"存入",
    r"(?<![a-z])deposit(?:s|ed|ing)?(?![a-z])",
    r"(?<![a-z])top(?:ped)?[ -]?up(?![a-z])",
)
_WITHDRAWAL = (
    r"(?<![卖支付售])出金(?!额)",
    r"(?<![卖售])出了[^，,。.?？!！]{0,3}?金(?!额)",
    r"提现",
    r"取现",
    r"(?<![a-z])withdr(?:aw|aws|awn|awal|awals|awing|ew)(?![a-z])",
)
# The shapes of asking what is still had ("还有多少", "how much ... have"), any thing named.
_LEFT_SHAPES = (
    r"(?:还有|还剩|剩下|剩余|还剩下|剩|有)(?:多少|几)",
    r"(?:还有|还剩|剩下|剩余|剩)",
    r"(?<![a-z])how (?:much|many)(?![a-z]).*"
    r"(?<![a-z])(?:have|got|hold|own|left|remaining)(?![a-z])",
    r"(?<![a-z])(?:do|have) (?:i|we) (?:still )?(?:have|got)(?![a-z])",
)
_CHINESE_NUMERALS = "零〇一二两三四五六七八九十百千万亿点"
_NUMBER = rf"(?:[0-9][0-9,]*(?:\.[0-9]+)?|[{_CHINESE_NUMERALS}]+)"


def _normal(text: str) -> str:
    """``text`` as it is matched: full-width forms made plain, letters in one case."""
    return unicodedata.normalize("NFKC", text).casefold()


def money_words(assets: Iterable[Asset] = ()) -> tuple[str, ...]:
    """Every word for a money: the base words, and each cash asset's code and name.

    For example, with a cash asset EUR named "Euro" in the ledger, "EUR"
    and "Euro" are words for a money too.
    """
    found = list(BASE_MONEY_WORDS)
    for asset in assets:
        if asset.kind is AssetKind.CASH:
            found += [asset.code, asset.name]
    return tuple(dict.fromkeys(word for word in found if word.strip()))


def _money(words: Sequence[str]) -> str:
    """One pattern for any of ``words``; a word of Latin letters stands on its own."""
    parts = []
    for word in sorted({_normal(word) for word in words}, key=len, reverse=True):
        escaped = re.escape(word)
        if word[-1].isascii() and word[-1].isalnum():
            escaped += r"(?![a-z])"
        if word[0].isascii() and word[0].isalpha():
            escaped = r"(?<![a-z])" + escaped
        parts.append(escaped)
    return "(?:" + "|".join(parts) + ")"


def _any(patterns: Sequence[str], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def names_a_balance(said: str) -> bool:
    """Whether ``said`` holds "余额" or "balance"; the caller then asks for the assets held."""
    return re.search(_BALANCE, _normal(said)) is not None


def may_ask_what_is_left(said: str) -> bool:
    """Whether ``said`` has the shape of asking what is still had, whatever is named.

    The caller asks the ledger for its cash assets only when this holds.
    """
    return _any(_LEFT_SHAPES, _normal(said))


def _left(text: str, words: Sequence[str]) -> bool:
    money = _money(words)
    patterns = (
        rf"(?:还有|还剩|剩下|剩余|还剩下|剩|有)(?:多少|几)(?:个|块)?\s*{money}",
        rf"{money}\s*(?:还有|还剩|剩下|剩余|还剩下|剩)",
        rf"(?<![a-z])how (?:much|many) {money} (?:do|does|did|have|can) (?:i|we) "
        r"(?:still )?(?:have|got|hold|own)(?![a-z])",
        rf"{money} (?:left|remaining)(?![a-z])",
        rf"(?<![a-z])(?:do|have) (?:i|we) (?:still )?(?:have|got) (?:any |enough |some )?{money}",
    )
    return _any(patterns, text)


def held_names(assets: Iterable[Asset]) -> tuple[str, ...]:
    """Every name of the ledger's assets that are not cash: codes, names and lent names.

    For example, with BTC in the ledger: "BTC", "Bitcoin", "比特币", "大饼".
    """
    listed = tuple(assets)
    held = {asset.code for asset in listed if asset.kind is not AssetKind.CASH}
    sayings = names_of(listed).sayings()
    return tuple(dict.fromkeys(name for name, code in sayings if code in held and name.strip()))


def _attached_balance(text: str, held: Sequence[str]) -> str:
    """``text`` with every "余额" or "balance" attached to an asset that is not cash taken out.

    Attached is "ETH 余额", "英伟达的余额", "BTC balance", "ETH's balance" and
    "balance of ETH"; "余额够不够买英伟达" is not.
    """
    if not held:
        return text
    asset = _money(held)
    for pattern in (
        rf"{asset}\s*(?:的|'s|’s)?\s*{_BALANCE}",
        rf"{_BALANCE}\s*(?:of|for|in)\s+(?:my\s+|the\s+)?{asset}",
    ):
        text = re.sub(pattern, " ", text)
    return text


def cash_question(
    said: str, words: Sequence[str] = BASE_MONEY_WORDS, held: Sequence[str] = ()
) -> CashAsk | None:
    """Which kind of question about cash ``said`` is, or ``None`` when it is none.

    ``words`` are the words for a money (``money_words``); ``held`` the names
    of the assets that are not cash (``held_names``), so that "ETH 余额" is a
    holding, not cash. The kinds are tried in the order of ``CashAsk``; the
    first that fits is given.
    """
    text = _normal(said)
    if _any(_CASH, text) or re.search(_BALANCE, _attached_balance(text, held)):
        return CashAsk.CASH
    if _left(text, words):
        return CashAsk.LEFT
    if _any(_DEPOSIT, text):
        return CashAsk.DEPOSIT
    if _any(_WITHDRAWAL, text):
        return CashAsk.WITHDRAWAL
    return None


def figures_beside_money(
    text: str, words: Sequence[str] = BASE_MONEY_WORDS
) -> tuple[tuple[str, str], ...]:
    """Every number in ``text`` written right beside a money word: the words found, the number.

    For example, "你还有 50 USDT" gives (("50 usdt", "50"),); "可以问我 10 月的交易"
    gives none, since no money stands beside the 10.
    """
    normal = _normal(text)
    money = _money(words)
    number = rf"(?<![0-9a-z.])(?P<number>{_NUMBER})(?![0-9])"
    found: list[tuple[str, str]] = []
    for pattern in (
        rf"{number}\s*(?:个|块)?\s*{money}",
        rf"{money}\s*[:：]?\s*{number}",
    ):
        found += [(one.group(0), one.group("number")) for one in re.finditer(pattern, normal)]
    return tuple(found)


def figure_beside_money(text: str, words: Sequence[str] = BASE_MONEY_WORDS) -> str | None:
    """The first number in ``text`` written right beside a money word, or ``None``."""
    found = figures_beside_money(text, words)
    return found[0][0] if found else None
