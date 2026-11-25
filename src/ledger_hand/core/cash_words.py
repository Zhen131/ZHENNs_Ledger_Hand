"""The words that tell a question about cash, and a figure the model made up beside a money.

This module tells, from the user's own words alone, whether they ask about
cash. It asks no ledger and no model. None of the eight tools the
assistant uses reads a cash balance, a deposit or a withdrawal, so such a
question is answered by the program itself, truthfully
(``flows.cash_question``).

What a question about cash is (``CashAsk``), one kind each:

- ``CASH``: cash or a balance named outright: "现金", "余额", "可用资金",
  "cash", "balance", "buying power". "balance" is a word of its own:
  "rebalance" and "balanced" are not it. A sentence with a balance in it
  is judged by three rules, in order (second rework, 2026-11-25): asked
  whether it is enough to buy ("够不够", "够买", "enough ... buy",
  "afford"), it is cash; else, naming anywhere an asset that is not cash
  (the names handed in as ``held``) or a word that counts an asset ("股",
  "币", "个", "枚", "份", "shares", "coins", "stocks", "tokens"), it is
  not; else it is cash.
- ``LEFT``: how much of a money is still had: "我还有多少USDT",
  "账上还剩多少美元", "USDT还剩多少", "how much USD do I have left",
  "do I still have any USDT". The money is one of ``money_words``: the
  nicknames of ``ledger_table.MONEY_NICKNAMES``, "钱", "money", and the
  code and name of each asset the ledger lists as cash. No money is
  written in here for good: what the ledger calls cash is handed in.
- ``DEPOSIT``: money put in: "入金", "入了多少金", "充值", "存入",
  "deposit", "top up". "买入金额", "收入金额", "买入了30美金" are not it.
- ``WITHDRAWAL``: money taken out: "出金", "出了多少金", "提现", "取现",
  "withdraw". "卖出金额", "支出金额" are not it.

What it does not catch (``docs/known-gaps.md``): a question that names no
money and none of these words ("我还能买多少BTC", "how much do I have left"),
or that names a coin rather than a money ("我还有多少BTC" is a holding, and
goes to the model as before).

``unsaid_cash_figure`` is the check made of the model's words when nothing
was looked up: words that name a money (a word for one, or "现金", "余额",
"cash", "balance") and hold any number the user never said in the chat,
compared by value ("一千" is 1000, "fifty" is 50), so that no figure the
model made up is ever said as cash.

Why the words are in one place: catching the question and the check of
the model's words must use the same list, or one would know a money the
other does not. (The product owner, 2026-11-25: asked about cash, say
truthfully that it cannot be looked up.)

Names defined here: ``CashAsk``, ``BASE_MONEY_WORDS``, ``money_words``,
``held_names``, ``names_a_balance``, ``may_ask_what_is_left``,
``cash_question``, ``figures_in`` and ``unsaid_cash_figure``.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from collections.abc import Iterable, Sequence
from decimal import Decimal, InvalidOperation

from ledger_hand.core.ledger_records import Asset, AssetKind
from ledger_hand.core.ledger_table import MONEY_NICKNAMES, names_of
from ledger_hand.core.numbers import Recognised, read_number


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
# "余额" and "balance": cash unless the sentence names an asset held (``_balance_is_cash``).
_BALANCE = r"(?:余额|(?<![a-z])balances?(?![a-z]))"
_DEPOSIT = (
    r"(?<![收投买录输转加])入金(?!额)",
    r"(?<!买)入了[^，,。.?？!！]{0,3}?金(?!额)",
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


# Asking whether the money is enough to buy something: a balance asked so is cash.
_AFFORD = (
    r"够不够",
    r"够[^，,。.?？!！]{0,6}买",
    r"(?<![a-z])enough(?![a-z]).*(?<![a-z])buy(?![a-z])",
    r"(?<![a-z])afford(?![a-z])",
)
# Words that count an asset: a balance said with one is of that asset, not cash.
_COUNTERS = (
    r"股",
    r"币",
    r"个",
    r"枚",
    r"份",
    r"(?<![a-z])(?:shares?|coins?|stocks?|tokens?)(?![a-z])",
)


def _balance_is_cash(text: str, held: Sequence[str]) -> bool:
    """Whether a balance named in ``text`` asks about cash (the second rework, 2026-11-25).

    Asked whether it is enough to buy: cash, whatever is named. Otherwise
    any name of an asset that is not cash, or a word that counts an asset
    ("股", "个", "shares"), anywhere in the sentence: not cash. Else cash.
    """
    if _any(_AFFORD, text):
        return True
    if held and re.search(_money(held), text):
        return False
    return not _any(_COUNTERS, text)


def cash_question(
    said: str, words: Sequence[str] = BASE_MONEY_WORDS, held: Sequence[str] = ()
) -> CashAsk | None:
    """Which kind of question about cash ``said`` is, or ``None`` when it is none.

    ``words`` are the words for a money (``money_words``); ``held`` the names
    of the assets that are not cash (``held_names``), so that "余额里 ETH 还有
    几个" is a holding, not cash. The kinds are tried in the order of ``CashAsk``; the
    first that fits is given.
    """
    text = _normal(said)
    if _any(_CASH, text):
        return CashAsk.CASH
    if re.search(_BALANCE, text) and _balance_is_cash(text, held):
        return CashAsk.CASH
    if _left(text, words):
        return CashAsk.LEFT
    if _any(_DEPOSIT, text):
        return CashAsk.DEPOSIT
    if _any(_WITHDRAWAL, text):
        return CashAsk.WITHDRAWAL
    return None


_CASH_NAMES = r"(?:现金|余额|(?<![a-z])(?:cash|balances?)(?![a-z]))"
_SAID_NUMBER = re.compile(
    rf"[0-9][0-9,]*(?:\.[0-9]+)?(?:[万亿千]|[kw](?![a-z]))?|[{_CHINESE_NUMERALS}]+"
)
_ONES = {
    word: value
    for value, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
    )
}
_TENS = {
    word: value * 10
    for value, word in enumerate(
        ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"], start=2
    )
}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}
_WORD_NUMBER = re.compile(
    r"(?<![a-z])(?:(?:a|and|" + "|".join((*_ONES, *_TENS, *_SCALES)) + r")(?:[ -]+|(?![a-z])))+",
)


def _spelled(words: str) -> Decimal | None:
    """An English number spelt in words ("fifty", "a thousand", "twenty-five"), or ``None``."""
    total, current, seen = 0, 0, False
    parts = [part for part in re.split(r"[ -]+", words.strip()) if part]
    for index, part in enumerate(parts):
        if part in _ONES or part in _TENS:
            current += _ONES.get(part, 0) + _TENS.get(part, 0)
            seen = True
        elif part in _SCALES:
            scale = _SCALES[part]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            seen = True
        elif part == "a" and index + 1 < len(parts) and parts[index + 1] in _SCALES:
            current = 0
    return Decimal(total + current) if seen else None


def figures_in(text: str) -> tuple[tuple[str, Decimal], ...]:
    """Every number in ``text`` as written and its value: digits, Chinese and English words.

    For example, "1万美元" is 10000, "一千" is 1000, "fifty" is 50 and
    "1,000.0" is 1000. A Chinese numeral the reader cannot read is left out;
    English words beyond 0 to 99, hundred, thousand and million are not read.
    """
    normal = _normal(text)
    found: list[tuple[str, Decimal]] = []
    for match in _SAID_NUMBER.finditer(normal):
        written = match.group(0)
        reading = read_number(written)
        if isinstance(reading, Recognised):
            found.append((written, reading.value))
            continue
        digits = re.match(r"[0-9][0-9,]*(?:\.[0-9]+)?", written)
        if digits is not None:
            try:
                found.append((digits.group(0), Decimal(digits.group(0).replace(",", ""))))
            except InvalidOperation:
                continue
    for match in _WORD_NUMBER.finditer(normal):
        value = _spelled(match.group(0))
        if value is not None:
            found.append((match.group(0).strip(), value))
    return tuple(found)


def unsaid_cash_figure(
    reply: str, words: Sequence[str] = BASE_MONEY_WORDS, user_said: Sequence[str] = ()
) -> str | None:
    """A number in ``reply`` the user never said, when ``reply`` also names a money; else ``None``.

    The reply names a money by a word for one (``words``) or by "现金",
    "余额", "cash" or "balance", anywhere; the number need not stand beside
    it (the second rework, 2026-11-25). Numbers are compared by value, so
    "一千" is the user's "1000". For example, "你的 USDT 余额是 50" gives "50"
    when the user never said 50.
    """
    normal = _normal(reply)
    if not (re.search(_money(words), normal) or re.search(_CASH_NAMES, normal)):
        return None
    said = {value for text in user_said for _, value in figures_in(text)}
    for written, value in figures_in(reply):
        if value not in said:
            return written
    return None
