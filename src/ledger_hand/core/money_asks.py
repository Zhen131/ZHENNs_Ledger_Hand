"""The words that tell money the assistant does not record, and a balance asked of any money.

This module reads the user's own words only. It asks no ledger and no
model; whoever calls it hands in what the ledger lists. It holds two
readings, kept apart from the question about cash (``cash_words``), which
it never changes (decided on 2026-11-26):

``statement`` tells something the user says was done that the assistant
does not record, said, not asked. Four kinds (``Manual``):

- a deposit: "入金", "充值", "存入", "入了500美金" (up to eight signs
  between "入了" and "金"), "转入了500U", "deposit", "top up". Not "买入金额",
  "收入", "投入", nor "买入了30美金" (a buy).
- a withdrawal: "出金", "提现", "取现", "出了200美金", "withdraw", "cash
  out". Not "卖出金额", "卖出了", "支出".
- an exchange of moneys: a verb of exchanging ("换成", "兑换", "换了",
  "convert", "exchange") with two moneys named, and no coin or share named
  at all ("用100 USDT换了0.001个BTC" is a buy). "换汇费", "FX fee" and
  "汇率转换的费用" are fees, not an exchange.
- a dividend: "分红", "派息", "股息", "dividend".

It is a statement only when no shape of a question or a request is in it
("多少", "几", "吗", "?", "how much", "what", "查", "看", "show", ...): a
question goes to the question about cash, as before. Whether a buy or a
sell is spoken of beside it ("买", "卖", "bought", "sold") is said too, so
that the trade is still recorded and only the rest is said to be recorded
by hand.

``left_asked`` tells "how much of a money is still had" for any money of
``ledger_table.MONEY_WORDS`` and ``VAGUE_MONEY_WORDS`` ("我还有多少欧元",
"我还剩多少EUR", "我还有多少福林"), and ``named_money`` reads which money
was named. "欧" alone is the euro only right after a number or right
beside "还有多少" and the like: "欧易还有多少币" names no money.

Why: the ledger records deposits, withdrawals, exchanges and dividends on
its own page, and the assistant proposes none of them (the product
owner's rule of 2026-11-25); asked of a money the question about cash
does not know, the user still gets the ledger's balances (decided on
2026-11-26).

Names defined here: ``Manual``, ``Statement``, ``statement``,
``may_be_exchange``, ``asks_or_requests``, ``left_asked``, ``named_money``
and ``money_named``.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ledger_hand.core.ledger_table import MONEY_WORDS, VAGUE_MONEY_WORDS

_VAGUE = "vague"
# "欧" is the euro only beside a number or a shape of "how much is left".
_EURO_SIGN = "欧"


class Manual(enum.Enum):
    """A kind of money moved that the assistant does not record; its value names it plural."""

    DEPOSIT = "deposits"
    WITHDRAWAL = "withdrawals"
    EXCHANGE = "currency exchanges"
    DIVIDEND = "dividends"


@dataclass(frozen=True)
class Statement:
    """What the user said was done and is recorded by hand: each kind, and whether a buy or
    a sell was spoken of beside it."""

    kinds: tuple[Manual, ...]
    with_trade: bool


def _normal(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


_BREAK = r"[^，,。.?？!！;；]"

_QUESTION = (
    r"多少",
    r"几",
    r"吗",
    r"什么",
    r"怎么",
    r"哪",
    r"[?？]",
    r"(?<![a-z])how(?![a-z])",
    r"(?<![a-z])(?:what|which|whether)(?![a-z])",
    r"(?<![a-z])(?:did|do|does|have|has|can|could|was|were|is|are) (?:i|we|you)(?![a-z])",
)
_REQUEST = (
    r"查",
    r"看",
    r"告诉我",
    r"列出",
    r"列一下",
    r"统计",
    r"算一下",
    r"(?<![a-z])(?:show|list|tell me|check|find|look up)(?![a-z])",
)
_DEPOSIT = (
    r"(?<![收投买录输转加])入金(?!额)",
    rf"(?<![买收投])入了{_BREAK}{{0,8}}?金(?!额)",
    r"转入了?\s*[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:u|usdt)(?![a-z])",
    r"充值",
    r"存入",
    r"(?<![a-z])deposit(?:s|ed|ing)?(?![a-z])",
    r"(?<![a-z])top(?:ped|s)?[ -]?up(?![a-z])",
)
_WITHDRAWAL = (
    r"(?<![卖支付售])出金(?!额)",
    rf"(?<![卖售支付])出了{_BREAK}{{0,8}}?金(?!额)",
    r"提现",
    r"取现",
    r"(?<![a-z])withdr(?:aw|aws|awn|awal|awals|awing|ew)(?![a-z])",
    r"(?<![a-z])cash(?:ed|ing)? out(?![a-z])",
)
_DIVIDEND = (
    r"分红",
    r"派息",
    r"股息",
    r"(?<![a-z])dividends?(?![a-z])",
)
# A fee for exchanging is a fee of a trade, not an exchange: taken out first.
_EXCHANGE_FEES = (
    r"换汇费",
    r"汇率转换的?费用?",
    r"(?<![a-z])(?:fx|exchange|conversion|currency) fees?(?![a-z])",
    r"(?<![a-z])exchange rates?(?![a-z])",
)
_EXCHANGE = (
    r"换成",
    r"兑换",
    r"换了",
    r"换汇",
    r"(?<![a-z])convert(?:s|ed|ing)?(?![a-z])",
    r"(?<![a-z])exchang(?:e|es|ed|ing)(?![a-z])",
)
_TRADE = (
    r"买",
    r"卖",
    r"购",
    r"抛",
    r"建仓",
    r"加仓",
    r"减仓",
    r"清仓",
    r"(?<![a-z])(?:bought|sold|buy|buys|buying|sell|sells|selling|purchas(?:e|ed|es|ing))"
    r"(?![a-z])",
)
# Words of a kind that are not it: a buy's amount, an income, a sell's amount.
_NOT_A_KIND = (r"买入金额", r"卖出金额", r"收入金额")


def asks_or_requests(said: str) -> bool:
    """Whether ``said`` has the shape of a question or of a request ("多少", "查", "show")."""
    text = _normal(said)
    return _any(_QUESTION, text) or _any(_REQUEST, text)


def _money_words(extra: Sequence[tuple[str, str]] = ()) -> tuple[tuple[str, str], ...]:
    """Every word for a money with its code (``_VAGUE`` for a vague one), longest first.

    "欧" alone is left out: it is read beside a number or a shape of asking.
    """
    pairs = [
        *(pair for pair in MONEY_WORDS if pair[0] != _EURO_SIGN),
        *((word, _VAGUE) for word in VAGUE_MONEY_WORDS),
        *extra,
    ]
    seen: dict[str, str] = {}
    for word, code in pairs:
        if word.strip():
            seen.setdefault(_normal(word), code)
    return tuple(sorted(seen.items(), key=lambda pair: len(pair[0]), reverse=True))


def _escaped(word: str) -> str:
    escaped = re.escape(word)
    if word[-1].isascii() and word[-1].isalnum():
        escaped += r"(?![a-z])"
    if word[0].isascii() and word[0].isalnum():
        escaped = r"(?<![a-z])" + escaped
    return escaped


def _money_pattern(pairs: Sequence[tuple[str, str]]) -> str:
    return "(?:" + "|".join(_escaped(word) for word, _ in pairs) + ")"


_SHAPES = r"(?:还有|还剩|剩下|剩余|还剩下|剩)"


def _euro_places(text: str) -> list[int]:
    """Where "欧" alone stands for the euro in ``text``."""
    patterns = (
        rf"[0-9]\s*({_EURO_SIGN})(?![元洲易])",
        rf"{_SHAPES}(?:多少|几)?(?:个|块)?\s*({_EURO_SIGN})(?![元洲易])",
        rf"(?:^|[^\w])({_EURO_SIGN})(?![元洲易])\s*{_SHAPES}",
    )
    return sorted({match.start(1) for pattern in patterns for match in re.finditer(pattern, text)})


def money_named(said: str, extra: Sequence[tuple[str, str]] = ()) -> tuple[str, ...]:
    """Each money ``said`` names, by code, in the order first named; ``"vague"`` for a vague word.

    ``extra`` are more words with their codes: the code and name of each
    cash asset of the ledger. For example, "把100欧元换成了108美元" names
    ("EUR", "USD"); "100U换成美金" names ("USDT", "vague").
    """
    text = _normal(said)
    pairs = _money_words(extra)
    codes = dict(pairs)
    found: list[tuple[int, str]] = []
    for match in re.finditer(_money_pattern(pairs), text):
        found.append((match.start(), codes[match.group(0)]))
    found += [(place, "EUR") for place in _euro_places(text)]
    ordered = [code for _, code in sorted(found)]
    return tuple(dict.fromkeys(ordered))


def _held(text: str, held: Sequence[str]) -> bool:
    names = [name for name in held if name.strip()]
    if not names:
        return False
    pattern = "(?:" + "|".join(_escaped(_normal(name)) for name in names) + ")"
    return re.search(pattern, text) is not None


def may_be_exchange(said: str) -> bool:
    """Whether ``said`` may tell an exchange: a verb of exchanging and two moneys named.

    The caller then asks the ledger for its assets, to know the coins and
    shares it holds, before ``statement`` judges it.
    """
    text = _normal(said)
    for fee in _EXCHANGE_FEES:
        text = re.sub(fee, " ", text)
    return _any(_EXCHANGE, text) and len(money_named(text)) >= 2


def statement(
    said: str, held: Sequence[str] = (), extra: Sequence[tuple[str, str]] = ()
) -> Statement | None:
    """What ``said`` tells was done that is recorded by hand, or ``None``.

    ``held`` are the names of the coins and shares the ledger knows, and
    the built-in coins' names; ``extra`` the ledger's cash moneys, each word
    with its code. A question or a request is no statement.
    """
    if asks_or_requests(said):
        return None
    text = _normal(said)
    for words in _NOT_A_KIND:
        text = text.replace(words, " ")
    kinds: list[Manual] = []
    if _any(_DEPOSIT, text):
        kinds.append(Manual.DEPOSIT)
    if _any(_WITHDRAWAL, text):
        kinds.append(Manual.WITHDRAWAL)
    if _exchange(text, held, extra):
        kinds.append(Manual.EXCHANGE)
    if _any(_DIVIDEND, text):
        kinds.append(Manual.DIVIDEND)
    if not kinds:
        return None
    return Statement(kinds=tuple(kinds), with_trade=_any(_TRADE, text))


def _exchange(text: str, held: Sequence[str], extra: Sequence[tuple[str, str]]) -> bool:
    for fee in _EXCHANGE_FEES:
        text = re.sub(fee, " ", text)
    if not _any(_EXCHANGE, text):
        return False
    if len(money_named(text, extra)) < 2:
        return False
    return not _held(text, held)


def left_asked(said: str, extra: Sequence[tuple[str, str]] = ()) -> bool:
    """Whether ``said`` asks how much of some money is still had, any money of the tables.

    For example "我还有多少欧元", "我还剩多少EUR", "欧还剩多少", "how much
    euro do I have left". Not "欧易还有多少币", nor "我还有多少BTC".
    """
    text = _normal(said)
    money = _money_pattern(_money_words(extra))
    patterns = (
        rf"{_SHAPES}(?:多少|几)(?:个|块)?\s*{money}",
        rf"{money}\s*{_SHAPES}",
        rf"(?<![a-z])how (?:much|many) {money} (?:do|does|did|have|can) (?:i|we) "
        r"(?:still )?(?:have|got|hold|own)(?![a-z])",
        rf"{money} (?:left|remaining)(?![a-z])",
        rf"(?<![a-z])(?:do|have) (?:i|we) (?:still )?(?:have|got) (?:any |enough |some )?{money}",
    )
    if _any(patterns, text):
        return True
    return _any(
        (
            rf"{_SHAPES}(?:多少|几)(?:个|块)?\s*{_EURO_SIGN}(?![元洲易])",
            rf"(?:^|[^\w]){_EURO_SIGN}(?![元洲易])\s*{_SHAPES}",
        ),
        text,
    )


def named_money(said: str, extra: Sequence[tuple[str, str]] = ()) -> str | None:
    """The one money ``said`` names outright, by code, or ``None``.

    ``None`` when it names none, names a vague word ("美金", "刀", "$"),
    which is never picked for USDT or the dollar, or names more than one.
    """
    named = money_named(said, extra)
    if len(named) != 1 or named[0] == _VAGUE:
        return None
    return named[0]
