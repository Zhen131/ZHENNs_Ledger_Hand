"""What the golden book of version 1 holds, written out by hand.

The golden book is a committed SQLite file made by this program's own store
at version 1 (``tests/storage/golden/book-v1.sqlite3``), with a text dump of
it beside it (``book-v1.sql``) so that the hygiene scan, which only reads
text, can see what is inside. Both are never changed once committed: a new
version of the book gets a golden sample of its own.

Everything in it is invented. Between them, its three trades have: times
known to the day, the minute and the second; an amount worked out by the
program (the quantity once, the total once) and none worked out; a fee in
USDT, a fee of zero and a fee in a third coin; a coin the user confirmed;
one trade exported and two not; a platform and a note, each given and not
given; and passages in Chinese, one of them with two trades.

The values below are written out in full, not built by the check of a draft,
so that what the file is expected to hold never moves with the program.

Names defined here: ``PASSAGE_A``, ``PASSAGE_B``, ``FINGERPRINT_A``,
``FINGERPRINT_B``, ``SAVED_A``, ``SAVED_B``, ``EXPORTED_A``, ``TRADE_A1``,
``TRADE_B1``, ``TRADE_B2``, ``LISTED``, ``COINS`` and ``GOLDEN_DIR``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from ledger_hand.core.book import ConfirmedCoin, ListedTrade
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import Amount, OccurredTime, Side, TimePrecision, TradeRecord

GOLDEN_DIR = Path(__file__).parent / "golden"

PASSAGE_A = "10月2日在 OKX 花 1000 刀买了以太，价格 2500，手续费 0.5 BNB"
PASSAGE_B = (
    "昨天晚上 9 点 40 在币安买了 0.02 BTC，94900，手续费 2 USDT；"
    "21:41:30 又卖了 1000 个 PIKA，0.05 一个，共 50，手续费 0，我觉得要涨"
)
# The fingerprints of the two passages, as the program works them out.
FINGERPRINT_A = "sha256:04df1d42cc9f233567f7922e180f7baaa2e1a4e9590b2bde80f0c7fd6764fe5e"
FINGERPRINT_B = "sha256:5bba1dd4d626bd94f9328afa7a66cc140f394c4f6f8c0e4c80bc480846a36da9"

UTC = timezone.utc
BUDAPEST_SUMMER = timezone(timedelta(hours=2))
SAVED_A = datetime(2026, 10, 2, 19, 5, 10, 250000, tzinfo=UTC)
EXPORTED_A = datetime(2026, 10, 3, 7, 15, 42, 250, tzinfo=UTC)
SAVED_B = datetime(2026, 10, 8, 18, 30, 15, 123456, tzinfo=UTC)

TRADE_A1 = StoredTrade(
    id="hand-3f6c1e2a-9b7d-4c58-a1e0-5d2b8f4c7a93",
    record=TradeRecord(
        side=Side.BUY,
        coin="ETH",
        quantity=Decimal("0.4"),
        price=Decimal("2500"),
        total=Decimal("1000"),
        derived=Amount.QUANTITY,
        fee=Decimal("0.5"),
        fee_coin="BNB",
        occurred=OccurredTime(date(2026, 10, 2), TimePrecision.DAY, "Europe/Budapest"),
        raw_text=PASSAGE_A,
        platform="OKX",
        note=None,
    ),
    created_at=SAVED_A,
    updated_at=SAVED_A,
)
TRADE_B1 = StoredTrade(
    id="hand-8d2a4f61-0c3e-4b9a-8e7f-1a5c6d3b2e08",
    record=TradeRecord(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        total=Decimal("1898"),
        derived=Amount.TOTAL,
        fee=Decimal("2"),
        fee_coin="USDT",
        occurred=OccurredTime(
            datetime(2026, 10, 7, 21, 40, tzinfo=BUDAPEST_SUMMER),
            TimePrecision.MINUTE,
            "Europe/Budapest",
        ),
        raw_text=PASSAGE_B,
        platform="Binance",
        note=None,
    ),
    created_at=SAVED_B,
    updated_at=SAVED_B,
)
TRADE_B2 = StoredTrade(
    id="hand-c41e9b7a-6d2f-4e83-b0a5-9f3c2d8e1b76",
    record=TradeRecord(
        side=Side.SELL,
        coin="PIKA",
        quantity=Decimal("1000"),
        price=Decimal("0.05"),
        total=Decimal("50"),
        derived=None,
        fee=Decimal("0"),
        fee_coin="USDT",
        occurred=OccurredTime(
            datetime(2026, 10, 7, 21, 41, 30, tzinfo=BUDAPEST_SUMMER),
            TimePrecision.SECOND,
            "Europe/Budapest",
        ),
        raw_text=PASSAGE_B,
        platform=None,
        note="我觉得要涨",
    ),
    created_at=SAVED_B,
    updated_at=SAVED_B,
)

LISTED = (
    ListedTrade(trade=TRADE_A1, exported_at=EXPORTED_A),
    ListedTrade(trade=TRADE_B1),
    ListedTrade(trade=TRADE_B2),
)
COINS = (ConfirmedCoin(symbol="PIKA", confirmed_at=SAVED_B),)
