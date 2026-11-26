"""The exam book: the demo book, and seven more trades the exam's questions and changes need.

Every sentence of the exam (recording in three tiers, questions about the
ledger, changes and deletions) is said against this book, in a fake
ledger of its own (``exam_ledger``), so that what one sentence finds is
what the next would find too. It takes the demo book's assets, trades and
market prices as they are (``ledger.demo_book``, which stays as it is) and
adds these trades, every number made up:

- ``t-21``: an ETH buy on the afternoon of 9 October 2026, its fee taken
  in ETH, for E-01 (a fee to change);
- ``t-22`` and ``t-23``: the same MSFT buy twice, at noon on 12 November
  2026, for E-03 (a trade recorded twice, one to delete);
- ``t-24`` and ``t-25``: two SOL buys in September 2026, for E-05 (more
  than one trade matches, so the program must ask which);
- ``t-26``: a BTC buy on 23 November 2026, the day before the exam's
  moment, for E-07 (yesterday's trade, its price to change);
- ``t-27``: a BTC buy in November 2026, for the hidden half.

Each new trade uses the money the demo book prices its asset in (USDT for
a coin, USD for a share), so the money guessed for a vague word ("美金")
is, for every recording sentence, what it is against the demo book; a
test sees to it. The words each new trade was recorded from are made up
too, agree with its figures, and copy no sentence of the exam.

Names defined here: ``EXAM_ADDED``, ``EXAM_TRADES`` and ``exam_ledger``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.trade import Side
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES, DEMO_TRADES
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ZONE

_BUDAPEST = ZoneInfo(INVENTED_ZONE)


def _buy(
    when: tuple[int, int, int, int, int],
    asset: str,
    amounts: tuple[str, str, str],
    quote: str,
    fee: tuple[str, str],
    platform: str,
    raw_text: str,
) -> TradeFacts:
    """One invented buy: ``amounts`` are quantity, price, total; ``fee`` its amount and asset."""
    quantity, price, total = (Decimal(amount) for amount in amounts)
    return TradeFacts(
        occurred=datetime(*when, tzinfo=_BUDAPEST),
        side=Side.BUY,
        asset=asset,
        quantity=quantity,
        price=price,
        total=total,
        quote=quote,
        fee=Decimal(fee[0]),
        fee_asset=fee[1],
        platform=platform,
        note="",
        raw_text=raw_text,
        zone=INVENTED_ZONE,
        date_only=False,
        cost_rate=None,
    )


_MSFT_TWICE = _buy(
    (2026, 11, 12, 12, 5),
    "MSFT",
    ("0.5", "437", "218.5"),
    "USD",
    ("1", "USD"),
    "Broker",
    "Bought 0.5 MSFT at 437 USD a share, 12 November 12:05, fee 1 USD.",
)

# The seven trades added, oldest identifier first.
EXAM_ADDED: tuple[tuple[str, TradeFacts], ...] = (
    (
        "t-21",
        _buy(
            (2026, 10, 9, 15, 20),
            "ETH",
            ("0.116", "2450", "284.2"),
            "USDT",
            ("0.000116", "ETH"),
            "Binance",
            "10月9号15:20在币安买了0.116个ETH，2450 USDT一个，手续费0.000116 ETH",
        ),
    ),
    ("t-22", _MSFT_TWICE),
    ("t-23", _MSFT_TWICE),
    (
        "t-24",
        _buy(
            (2026, 9, 8, 10, 30),
            "SOL",
            ("2", "150", "300"),
            "USDT",
            ("0.3", "USDT"),
            "Binance",
            "9月8号10:30在币安买了2个SOL，150 USDT一个，手续费0.3 USDT",
        ),
    ),
    (
        "t-25",
        _buy(
            (2026, 9, 22, 18, 0),
            "SOL",
            ("1.5", "210", "315"),
            "USDT",
            ("0.315", "USDT"),
            "OKX",
            "Bought 1.5 SOL at 210 USDT on OKX, 22 September 18:00, fee 0.315 USDT.",
        ),
    ),
    (
        "t-26",
        _buy(
            (2026, 11, 23, 20, 10),
            "BTC",
            ("0.001", "63000", "63"),
            "USDT",
            ("0.000001", "BTC"),
            "OKX",
            "11月23号20:10在OKX买了0.001个BTC，63000 USDT一个，手续费0.000001 BTC",
        ),
    ),
    (
        "t-27",
        _buy(
            (2026, 11, 20, 9, 45),
            "BTC",
            ("0.0006", "84000", "50.4"),
            "USDT",
            ("0.0000006", "BTC"),
            "OKX",
            "Bought 0.0006 BTC at 84000 USDT on OKX, 20 November 9:45, fee 0.0000006 BTC.",
        ),
    ),
)

EXAM_TRADES = (*DEMO_TRADES, *EXAM_ADDED)


def exam_ledger() -> FakeLedger:
    """A new fake ledger holding the exam book: the demo assets and prices, and its trades.

    It takes cards with cells left empty, as the real ledger does since
    2026-11-25, so that a sentence is measured against the ledger as it is.
    """
    ledger = FakeLedger(assets=DEMO_ASSETS, trades=EXAM_TRADES, prices=DEMO_MARKET_PRICES)
    return ledger.taking_cards()
