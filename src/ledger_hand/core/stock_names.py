"""The program's own table of common company names, and how a name said is matched to a code.

This module holds two things the assistant uses when the ledger's own list
does not know the name of an asset said ("微软的股票"):

- ``COMPANY_NAMES``: the Chinese names of common companies listed in the
  United States, each with the code or codes its shares trade under. It
  is fixed data, kept in the code; a row is only ever added.
- ``RememberedName``: a name the user once answered with a code, kept in
  a plain file on this machine (``flows.asset_names`` reads and writes
  it); this module only reads the entries handed to it.

``find_name`` matches one name, the answers remembered first and the table
second, so that a user's answer wins over the table. A name is matched
only whole: its trailing words for "share" or "company"
(``TAIL_WORDS``) are cut off first, at most twice, and what is left must
equal a name of the table, or an answer, exactly. Nothing is matched by a
part of a name or by being alike. Once matched, the code must be in the
ledger's own table; a table row whose codes the ledger lacks gives
``NameAbsent`` (the trade is not sent, and the user is told to add it
first), and one with more than one code in the ledger gives
``NameSeveral`` (the asset is asked, as before).

``worth_remembering`` says whether an answer to the question "which asset"
is kept: only a name the user said, of two characters or more, that is not
a word for a kind of asset (``GENERAL_WORDS``), a money or a built-in
coin's name, and an answer that is a code of the ledger's table.

Why a table and remembered answers, with the model doing nothing more:
the model, handed the ledger's list, matched names the ledger lacks to
assets it has ("谷歌" as AAPL), so that step stays off; the program
matching whole names cannot do that (decided on 2026-11-27).

This module reads no file, clock or setting: all is handed in.

Names defined here: ``COMPANY_NAMES``, ``TAIL_WORDS``, ``GENERAL_WORDS``,
``LEAST_NAME_LENGTH``, ``bare_name``, ``codes_named``, ``can_remember``,
``RememberedName``, ``NameMatched``, ``NameAbsent``, ``NameSeveral``,
``NameFound``, ``NameOutcome``, ``find_name`` and ``worth_remembering``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.coins import BUILT_IN_COINS, USDT_WORDS, spoken_key
from ledger_hand.core.ledger_limits import is_symbol
from ledger_hand.core.ledger_table import MONEY_WORDS, VAGUE_MONEY_WORDS
from ledger_hand.core.trade import PickedBy, PickedFrom

# Common companies listed on a stock exchange in the United States, by the
# Chinese name people call them, each with its codes there. Only a name
# known to be the company's common name is kept, and only a code that can
# be written as a ledger code (Berkshire Hathaway's "BRK.B" cannot). A
# company is added only as a row; changing or taking out a row needs a
# reason. Chosen on 2026-11-27 as large companies and household brands,
# not from any test sentence.
COMPANY_NAMES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Technology.
    ("苹果", ("AAPL",)),  # Apple Inc.
    ("微软", ("MSFT",)),  # Microsoft Corporation
    ("谷歌", ("GOOGL", "GOOG")),  # Alphabet Inc., class A and class C shares
    ("亚马逊", ("AMZN",)),  # Amazon.com, Inc.
    ("英伟达", ("NVDA",)),  # NVIDIA Corporation
    ("特斯拉", ("TSLA",)),  # Tesla, Inc.
    ("奈飞", ("NFLX",)),  # Netflix, Inc.
    ("网飞", ("NFLX",)),  # Netflix, Inc.: its other common Chinese name
    ("英特尔", ("INTC",)),  # Intel Corporation
    ("高通", ("QCOM",)),  # QUALCOMM Incorporated
    ("博通", ("AVGO",)),  # Broadcom Inc.
    ("甲骨文", ("ORCL",)),  # Oracle Corporation
    ("思科", ("CSCO",)),  # Cisco Systems, Inc.
    ("台积电", ("TSM",)),  # Taiwan Semiconductor Manufacturing Company Limited (ADR)
    ("阿斯麦", ("ASML",)),  # ASML Holding N.V.
    ("美光", ("MU",)),  # Micron Technology, Inc.
    ("德州仪器", ("TXN",)),  # Texas Instruments Incorporated
    ("应用材料", ("AMAT",)),  # Applied Materials, Inc.
    ("戴尔", ("DELL",)),  # Dell Technologies Inc.
    ("索尼", ("SONY",)),  # Sony Group Corporation (ADR)
    # Food, drink and things bought every day.
    ("可口可乐", ("KO",)),  # The Coca-Cola Company
    ("百事", ("PEP",)),  # PepsiCo, Inc.
    ("麦当劳", ("MCD",)),  # McDonald's Corporation
    ("星巴克", ("SBUX",)),  # Starbucks Corporation
    ("耐克", ("NKE",)),  # NIKE, Inc.
    ("迪士尼", ("DIS",)),  # The Walt Disney Company
    ("沃尔玛", ("WMT",)),  # Walmart Inc.
    ("开市客", ("COST",)),  # Costco Wholesale Corporation
    ("好市多", ("COST",)),  # Costco Wholesale Corporation: its other common Chinese name
    ("家得宝", ("HD",)),  # The Home Depot, Inc.
    ("宝洁", ("PG",)),  # The Procter & Gamble Company
    ("高露洁", ("CL",)),  # Colgate-Palmolive Company
    ("雅诗兰黛", ("EL",)),  # The Estée Lauder Companies Inc.
    # Health.
    ("强生", ("JNJ",)),  # Johnson & Johnson
    ("辉瑞", ("PFE",)),  # Pfizer Inc.
    ("默沙东", ("MRK",)),  # Merck & Co., Inc.
    ("礼来", ("LLY",)),  # Eli Lilly and Company
    ("艾伯维", ("ABBV",)),  # AbbVie Inc.
    ("安进", ("AMGN",)),  # Amgen Inc.
    ("吉利德", ("GILD",)),  # Gilead Sciences, Inc.
    ("莫德纳", ("MRNA",)),  # Moderna, Inc.
    ("联合健康", ("UNH",)),  # UnitedHealth Group Incorporated
    # Banks and payments.
    ("摩根大通", ("JPM",)),  # JPMorgan Chase & Co.
    ("高盛", ("GS",)),  # The Goldman Sachs Group, Inc.
    ("摩根士丹利", ("MS",)),  # Morgan Stanley
    ("美国银行", ("BAC",)),  # Bank of America Corporation
    ("花旗", ("C",)),  # Citigroup Inc.
    ("富国银行", ("WFC",)),  # Wells Fargo & Company
    ("贝莱德", ("BLK",)),  # BlackRock, Inc.
    ("黑石", ("BX",)),  # Blackstone Inc.
    ("万事达", ("MA",)),  # Mastercard Incorporated
    ("美国运通", ("AXP",)),  # American Express Company
    ("贝宝", ("PYPL",)),  # PayPal Holdings, Inc.
    # Industry, energy and cars.
    ("波音", ("BA",)),  # The Boeing Company
    ("通用电气", ("GE",)),  # GE Aerospace (General Electric Company until 2024)
    ("卡特彼勒", ("CAT",)),  # Caterpillar Inc.
    ("埃克森美孚", ("XOM",)),  # Exxon Mobil Corporation
    ("雪佛龙", ("CVX",)),  # Chevron Corporation
    ("福特", ("F",)),  # Ford Motor Company
    ("通用汽车", ("GM",)),  # General Motors Company
    ("优步", ("UBER",)),  # Uber Technologies, Inc.
    ("爱彼迎", ("ABNB",)),  # Airbnb, Inc.
    # Chinese companies listed in the United States.
    ("阿里巴巴", ("BABA",)),  # Alibaba Group Holding Limited
    ("京东", ("JD",)),  # JD.com, Inc.
    ("拼多多", ("PDD",)),  # PDD Holdings Inc.
    ("百度", ("BIDU",)),  # Baidu, Inc.
    ("网易", ("NTES",)),  # NetEase, Inc.
    ("蔚来", ("NIO",)),  # NIO Inc.
    ("小鹏", ("XPEV",)),  # XPeng Inc.
    ("理想汽车", ("LI",)),  # Li Auto Inc.
    ("哔哩哔哩", ("BILI",)),  # Bilibili Inc.
    ("腾讯音乐", ("TME",)),  # Tencent Music Entertainment Group
    ("携程", ("TCOM",)),  # Trip.com Group Limited
    ("唯品会", ("VIPS",)),  # Vipshop Holdings Limited
    ("富途", ("FUTU",)),  # Futu Holdings Limited
    ("微博", ("WB",)),  # Weibo Corporation
    ("爱奇艺", ("IQ",)),  # iQIYI, Inc.
    ("好未来", ("TAL",)),  # TAL Education Group
    ("新东方", ("EDU",)),  # New Oriental Education & Technology Group Inc.
    ("百胜中国", ("YUMC",)),  # Yum China Holdings, Inc.
)

# The words cut off the end of a name before it is looked up, longest
# first, so that "微软的股票" and "苹果公司" are looked up as "微软" and
# "苹果". Each still means the company's shares, or the company. A word
# is only ever added. "股" and "的" alone are not cut: "2股微软" keeps its
# "股" beside the number, and "微软的" with nothing after it was never
# heard, so cutting "的" would only let a longer name slip through.
TAIL_WORDS: tuple[str, ...] = (
    # "微软的股票", "苹果股票": the company's shares.
    "的股票",
    "股票",
    # "英特尔股份": the company's shares.
    "的股份",
    "股份",
    # "苹果公司", "百事公司": the company itself.
    "的公司",
    "公司",
    # "阿里巴巴集团": the company itself.
    "集团",
)

# At most two words are cut ("微软公司的股票" to "微软公司" to "微软"); no
# usual way of saying a name stacks three. Not measured.
_MOST_CUTS = 2

# Two: a name of one character ("苹", "微") would match too much else. Set
# on 2026-11-27; not measured.
LEAST_NAME_LENGTH = 2

# The words that name a kind of asset, a market or a form of product, never
# one company: none is ever remembered as a name, even when the user
# answered a code after one. A word is only ever added.
GENERAL_WORDS: tuple[str, ...] = (
    # Words for an asset or a share in general.
    "股票",
    "股",
    "股份",
    "公司",
    "资产",
    "币",
    "代币",
    "币种",
    "这个",
    "那个",
    "这只",
    "那只",
    "这笔",
    "那笔",
    "stock",
    "stocks",
    "share",
    "shares",
    "coin",
    "coins",
    "token",
    "tokens",
    "asset",
    "assets",
    "crypto",
    # Words for a market, a kind of asset or a form of product.
    "美股",
    "港股",
    "A股",
    "个股",
    "科技股",
    "蓝筹股",
    "中概股",
    "概念股",
    "龙头股",
    "基金",
    "指数",
    "ETF",
    "期权",
    "期货",
    "债券",
    "理财",
    "现货",
    "合约",
    "加密货币",
    "数字货币",
    "虚拟货币",
    "虚拟币",
    "fund",
    "funds",
    "option",
    "options",
    "future",
    "futures",
    "bond",
    "bonds",
)

_TABLE: dict[str, tuple[str, ...]] = {spoken_key(name): codes for name, codes in COMPANY_NAMES}
_TAILS = tuple(sorted((spoken_key(word) for word in TAIL_WORDS), key=len, reverse=True))
_GENERAL = frozenset(spoken_key(word) for word in GENERAL_WORDS)
_MONEY = frozenset(
    {spoken_key(word) for word, _ in MONEY_WORDS}
    | {spoken_key(word) for word in VAGUE_MONEY_WORDS}
    | set(USDT_WORDS)
)
_COIN_NAMES = frozenset(
    spoken_key(form) for coin in BUILT_IN_COINS for form in (coin.symbol, coin.name, *coin.aliases)
)


def bare_name(word: str) -> str | None:
    """The name ``word`` is looked up by: its lookup form with its trailing words cut off.

    This function cuts the longest of ``TAIL_WORDS`` off the end, at most
    twice. ``None`` when what is left is shorter than
    ``LEAST_NAME_LENGTH``. Example: "微软公司的股票" gives "微软"; "公司"
    gives ``None``.
    """
    name = spoken_key(word)
    for _ in range(_MOST_CUTS):
        tail = next((tail for tail in _TAILS if name.endswith(tail)), None)
        if tail is None:
            break
        name = name[: -len(tail)].strip()
    return name if len(name) >= LEAST_NAME_LENGTH else None


def codes_named(name: str) -> tuple[str, ...]:
    """The codes the table gives the bare ``name``; none when it has no such name."""
    return _TABLE.get(spoken_key(name), ())


def can_remember(name: str) -> bool:
    """Whether the bare ``name`` may stand for one asset in the user's answers.

    It may not when it is shorter than ``LEAST_NAME_LENGTH``, names a kind
    of asset (``GENERAL_WORDS``), is a word for money, is a built-in
    coin's name, or could be written as a code itself (that is matched as
    a code instead). Example: "小可" may; "美股" and "MSFT" may not.
    """
    key = spoken_key(name)
    return (
        len(key) >= LEAST_NAME_LENGTH
        and key not in _GENERAL
        and key not in _MONEY
        and key not in _COIN_NAMES
        and not is_symbol(key)
    )


@dataclass(frozen=True)
class RememberedName:
    """A name the user once answered with a code: the bare name, the code, and the day."""

    name: str
    code: str
    day: date


@dataclass(frozen=True)
class NameMatched:
    """The name names ``code``, an asset of the ledger; ``source`` says how it was found."""

    code: str
    source: PickedFrom


@dataclass(frozen=True)
class NameAbsent:
    """The table names the name's codes, and the ledger has none of them."""

    codes: tuple[str, ...]


@dataclass(frozen=True)
class NameSeveral:
    """The table names more than one code for the name that the ledger has."""

    codes: tuple[str, ...]


type NameFound = NameMatched | NameAbsent | NameSeveral


@dataclass(frozen=True)
class NameOutcome:
    """What came of one name: the words as the cell held them, the bare name, and what was found."""

    word: str
    name: str
    found: NameFound


def find_name(
    word: str,
    assets: AssetTable,
    remembered: Sequence[RememberedName] = (),
    *,
    table: bool,
) -> NameOutcome | None:
    """What the name ``word`` names, by the user's answers and then the table; or ``None``.

    This function looks only when ``assets`` is the ledger's table and
    neither finds ``word`` as an asset nor reads it as money, and it is
    not a built-in coin's name the ledger lacks. ``remembered`` are the
    user's answers for this kind of ledger; ``table`` says whether the
    table is used. An answer counts only while its code is in the
    ledger's table; the latest answer for a name wins. Example: with MSFT
    in the ledger, "微软的股票" gives MSFT from the table.
    """
    said = word.strip()
    if not assets.from_ledger or not said or assets.find(said) is not None:
        return None
    if assets.money(said).reading is not MoneyReading.NOT_MONEY or assets.is_shielded(said):
        return None
    name = bare_name(said)
    if name is None:
        return None
    for entry in reversed(remembered):
        coin = assets.find(entry.code)
        if spoken_key(entry.name) == name and coin is not None and coin.symbol == entry.code:
            source = PickedFrom(by=PickedBy.ANSWER, day=entry.day)
            return NameOutcome(said, name, NameMatched(entry.code, source))
    codes = codes_named(name) if table else ()
    if not codes:
        return None
    held = tuple(code for code in codes if _has(assets, code))
    if len(held) == 1:
        return NameOutcome(said, name, NameMatched(held[0], PickedFrom(by=PickedBy.TABLE)))
    if held:
        return NameOutcome(said, name, NameSeveral(held))
    return NameOutcome(said, name, NameAbsent(codes))


def _has(assets: AssetTable, code: str) -> bool:
    coin = assets.find(code)
    return coin is not None and coin.symbol == code


def worth_remembering(
    word: str | None, answered: str | None, passage: str, assets: AssetTable
) -> tuple[str, str] | None:
    """The bare name and the code to remember from an answer to "which asset", or ``None``.

    ``word`` is what the asset cell held before the answer, ``answered``
    what it holds after, ``passage`` the words the user said. Kept only
    when the name, its trailing words cut off, may be remembered
    (``can_remember``), is a part of what the user said, and the answer is
    a code of the ledger's table. Example: "小可" answered "KO", with KO in
    the ledger and "小可" said: ("小可", "KO").
    """
    if word is None or answered is None or not assets.from_ledger:
        return None
    name = bare_name(word)
    if name is None or not can_remember(name) or name not in spoken_key(passage):
        return None
    code = spoken_key(answered)
    if not _has(assets, code) or assets.money(code).reading is not MoneyReading.NOT_MONEY:
        return None
    return name, code
