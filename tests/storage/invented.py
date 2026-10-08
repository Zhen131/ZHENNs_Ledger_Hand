"""Invented trades to save, shared by the storage tests.

Between them they hold every case a saved trade must come back from intact:
times known to the day, the minute and the second, in two time zones; each
of the three amounts worked out by the program once, and none of them once;
a fee in USDT, a fee of zero, a fee in the coin sold, and a fee in a third
coin, neither USDT nor the coin traded; a coin the user confirmed; a platform
and a note, each given and not given; and original texts in Chinese. Each one goes through the real
check (``validation.check_draft``), so each is a record this program would
really produce.

Names defined here: ``BUDAPEST``, ``SHANGHAI``, ``NOW``, ``SAVED_AT``,
``COINS``, ``records``, ``stored`` and ``passage``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.book import ConfirmedCoin, PassageSave
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import check_draft

BUDAPEST = "Europe/Budapest"
SHANGHAI = "Asia/Shanghai"

# The current moment of the check, and the moment the trades are saved: with
# a part of a second, which a saved moment keeps.
NOW = datetime(2026, 10, 8, 20, 0, tzinfo=ZoneInfo(BUDAPEST))
SAVED_AT = datetime(2026, 10, 8, 18, 30, 15, 123456, tzinfo=timezone.utc)

# The coin table with one coin the user confirmed.
COINS = BUILT_IN_TABLE.with_confirmed("PIKA")


def _record(draft: TradeDraft) -> TradeRecord:
    result = check_draft(draft, COINS, NOW)
    if not isinstance(result, TradeRecord):
        raise AssertionError(f"the check did not accept an invented trade: {result}")
    return result


def records() -> dict[str, TradeRecord]:
    """Four invented records, by what sets each apart."""
    return {
        "day": _record(
            TradeDraft(
                side=Side.BUY,
                coin="以太",
                price=Decimal("2500"),
                total=Decimal("1000"),
                quote="刀",
                fee=Decimal("0.5"),
                fee_coin="BNB",
                occurred=OccurredTime(date(2026, 10, 2), TimePrecision.DAY, BUDAPEST),
                platform="OKX",
                raw_text="10月2日在 OKX 花 1000 刀买了以太，价格 2500，手续费 0.5 BNB",
            )
        ),
        "minute": _record(
            TradeDraft(
                side=Side.BUY,
                coin="BTC",
                quantity=Decimal("0.02"),
                price=Decimal("94900"),
                fee=Decimal("2"),
                fee_coin="USDT",
                occurred=OccurredTime(
                    datetime(2026, 10, 7, 21, 40, tzinfo=ZoneInfo(BUDAPEST)),
                    TimePrecision.MINUTE,
                    BUDAPEST,
                ),
                platform="Binance",
                raw_text="昨天晚上 9 点 40 在币安买了 0.02 BTC，94900，手续费 2 USDT",
            )
        ),
        "second": _record(
            TradeDraft(
                side=Side.SELL,
                coin="pika",
                quantity=Decimal("1000"),
                price=Decimal("0.05"),
                total=Decimal("50.00"),
                fee=Decimal("0"),
                fee_coin="USDT",
                occurred=OccurredTime(
                    datetime(2026, 10, 7, 21, 41, 30, tzinfo=ZoneInfo(SHANGHAI)),
                    TimePrecision.SECOND,
                    SHANGHAI,
                ),
                note="我觉得要涨",
                raw_text="昨晚 21:41:30 卖了 1000 PIKA，0.05 一个，共 50.00，手续费 0，我觉得要涨",
            )
        ),
        "price": _record(
            TradeDraft(
                side=Side.SELL,
                coin="SOL",
                quantity=Decimal("2"),
                total=Decimal("300"),
                fee=Decimal("0.01"),
                fee_coin="SOL",
                occurred=OccurredTime(date(2026, 10, 6), TimePrecision.DAY, SHANGHAI),
                platform="Bybit",
                note="止盈",
                raw_text="10月6日在 Bybit 卖了 2 个 SOL，一共 300 U，手续费 0.01 SOL，止盈",
            )
        ),
    }


def stored(identifier: str, record: TradeRecord, at: datetime = SAVED_AT) -> StoredTrade:
    return StoredTrade(id=identifier, record=record, created_at=at, updated_at=at)


def passage(
    fingerprint: str,
    *trades: StoredTrade,
    at: datetime = SAVED_AT,
    coins: tuple[str, ...] = (),
) -> PassageSave:
    """A save of ``trades`` from the passage ``fingerprint``, with ``coins`` confirmed at ``at``."""
    return PassageSave(
        fingerprint=fingerprint,
        saved_at=at,
        trades=trades,
        coins=tuple(ConfirmedCoin(symbol=symbol, confirmed_at=at) for symbol in coins),
    )
