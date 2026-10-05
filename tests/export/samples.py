"""Invented trades to export: the golden sample's, and the ledger tier's other samples.

Every trade here is made up and goes through the real check
(``validation.check_draft``) before it is saved, so each one is a record this
program would really produce. The current moment of that check, the moment of
the export and the program's name and version are fixed, so nothing depends
on the day the tests run.

- ``golden_trades``: the trades of the golden sample, a committed file that
  the export must reproduce byte for byte. They are never to be changed: a new
  format, or a new set of trades, gets a golden sample of its own.
- ``edge_trades``: trades at the edges of what the check lets through, to show
  that the ledger accepts whatever the check accepts.
- ``third_coin_fee_trades``: a buy whose fee was paid in a third coin, neither
  USDT nor the coin bought. The ledger accepts it, but does not count such a
  fee in the cost; whether this program should accept it is not settled, so it
  stays out of the golden sample.
- ``sell_only_trades``: a sale with no buy before it, which the ledger refuses
  for selling more than is held.
- ``broken_texts``: the golden sample's text with one mistake planted in each
  copy, which the ledger must refuse for exactly that mistake.
- ``every_zone_trades``: one trade recorded in each time zone this machine's
  zone database knows and a trade's time may be recorded in, to show that the
  ledger knows every such zone too.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import check_draft
from ledger_hand.export.backup import (
    BACKUP_FORMAT_VERSION,
    LEDGER_SCHEMA_VERSION,
    ExportRefused,
    export_backup,
)

BUDAPEST = "Europe/Budapest"
SHANGHAI = "Asia/Shanghai"

# The current moment of the check, the moment of the export, and the date
# on the machine that exports, which the ledger is also given as its today.
NOW = datetime(2026, 10, 4, 10, 0, tzinfo=ZoneInfo(BUDAPEST))
EXPORTED_AT = datetime(2026, 10, 4, 8, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 4)

# Fixed rather than the package's version, so that a new version of the
# program does not change the golden sample.
APP_NAME = "ledger-hand"
APP_VERSION = "0.1.0"

GOLDEN_FILE = (
    Path(__file__).parent
    / "golden"
    / f"backup-format-v{BACKUP_FORMAT_VERSION}-ledger-schema-v{LEDGER_SCHEMA_VERSION}.json"
)

GRINNING_FACE = "\N{GRINNING FACE}"


def utc(day: int, hour: int, minute: int, second: int = 0, microsecond: int = 0) -> datetime:
    """A bookkeeping moment in October 2026, in UTC."""
    return datetime(2026, 10, day, hour, minute, second, microsecond, tzinfo=timezone.utc)


# When a sample trade was saved, unless it says otherwise.
CREATED = utc(4, 7, 41)


def wall(
    zone: str,
    when: tuple[int, int, int, int, int],
    second: int | None = None,
    *,
    fold: int = 0,
) -> OccurredTime:
    """A moment read off the wall clock of ``zone``, to the minute or to the second."""
    year, month, day, hour, minute = when
    moment = datetime(year, month, day, hour, minute, second or 0, tzinfo=ZoneInfo(zone), fold=fold)
    precision = TimePrecision.MINUTE if second is None else TimePrecision.SECOND
    return OccurredTime(moment, precision, zone)


def day(year: int, month: int, number: int, zone: str = BUDAPEST) -> OccurredTime:
    return OccurredTime(date(year, month, number), TimePrecision.DAY, zone)


def record(
    draft: TradeDraft, coins: CoinTable = BUILT_IN_TABLE, now: datetime = NOW
) -> TradeRecord:
    """The record the check makes of ``draft``; a draft it does not accept is a mistake here."""
    result = check_draft(draft, coins, now)
    if not isinstance(result, TradeRecord):
        raise AssertionError(f"the check did not accept a sample trade: {result}")
    return result


def saved(
    identifier: str,
    draft: TradeDraft,
    coins: CoinTable = BUILT_IN_TABLE,
    created: datetime | None = None,
    updated: datetime | None = None,
    now: datetime = NOW,
) -> StoredTrade:
    """``draft`` checked and saved; created at the usual moment unless told otherwise."""
    created = CREATED if created is None else created
    return StoredTrade(
        id=identifier,
        record=record(draft, coins, now),
        created_at=created,
        updated_at=created if updated is None else updated,
    )


def exported(
    trades: list[StoredTrade], coins: CoinTable = BUILT_IN_TABLE, today: date = TODAY
) -> str:
    """The text of the file for ``trades``; a refusal is a mistake here."""
    text = export_backup(
        trades,
        coins,
        exported_at=EXPORTED_AT,
        today=today,
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )
    if isinstance(text, ExportRefused):
        raise AssertionError(f"the export refused sample trades: {text}")
    return text


def number(text: str) -> Decimal:
    return Decimal(text)


# --- the golden sample ------------------------------------------------------
#
# Between them, these four trades have: buys, and a buy followed by a sale of
# part of it; a fee of zero, a fee in USDT and fees in the coin itself, on a
# buy and on a sale; times known to the day, the minute and the second, in two
# time zones; a platform and a note, each given and not given; amounts worked
# out by the program; original texts in Chinese and in English; a coin with no
# market on Binance; and a change made after the creation, with a part of a
# second that is not written. They are handed over out of the order they
# happened in.


def golden_trades() -> list[StoredTrade]:
    """The trades of the golden sample, in the order they are handed to the export."""
    return [
        saved(
            "hand-trade-0001",
            TradeDraft(
                side=Side.BUY,
                coin="BTC",
                quantity=number("0.02"),
                price=number("94900"),
                fee=number("2"),
                fee_coin="USDT",
                occurred=wall(BUDAPEST, (2026, 10, 3, 21, 40)),
                platform="Binance",
                note="我觉得要涨",
                raw_text="昨天晚上 9 点 40 在币安买了 0.02 BTC，94900，手续费 2 USDT，我觉得要涨",
            ),
            created=utc(4, 7, 41),
        ),
        saved(
            "hand-trade-0002",
            TradeDraft(
                side=Side.SELL,
                coin="btc",
                quantity=number("0.01"),
                price=number("96000"),
                fee=number("0.00001"),
                fee_coin="BTC",
                occurred=wall(BUDAPEST, (2026, 10, 4, 9, 15), 30),
                raw_text="sold 0.01 BTC at 96,000 at 9:15:30, fee 0.00001 BTC",
            ),
            created=utc(4, 7, 42, 10),
            updated=utc(4, 7, 45, 12, 250_000),
        ),
        saved(
            "hand-trade-0003",
            TradeDraft(
                side=Side.BUY,
                coin="以太",
                price=number("2500"),
                total=number("1000"),
                quote="刀",
                fee=number("0"),
                occurred=day(2026, 10, 2),
                platform="OKX",
                raw_text="10月2日在 OKX 花 1000 刀买了以太，价格 2500，没有手续费",
            ),
            created=utc(4, 7, 43),
        ),
        saved(
            "hand-trade-0004",
            TradeDraft(
                side=Side.BUY,
                coin="门罗",
                quantity=number("3"),
                price=number("160.5"),
                fee=number("0.003"),
                fee_coin="XMR",
                occurred=wall(SHANGHAI, (2026, 10, 1, 14, 5)),
                note="长期拿着",
                raw_text="10/1 下午两点零五买了 3 个门罗，160.5 一个，手续费 0.003 XMR，长期拿着",
            ),
            created=utc(4, 7, 44),
        ),
    ]


def golden_text() -> str:
    """The export of the golden trades, as it is now."""
    return exported(golden_trades())


# --- edges ------------------------------------------------------------------

LONGEST_SYMBOL = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"


def edge_coins() -> CoinTable:
    """The built-in coins and two the user confirmed, one with the longest symbol there is."""
    return BUILT_IN_TABLE.with_confirmed("newcoin").with_confirmed(LONGEST_SYMBOL.lower())


def _longest_texts() -> dict[str, str]:
    """A platform, note and original text each exactly as long as the ledger allows.

    Lengths are as the ledger counts them: a face counts as two.
    """
    raw = "今天买币" + GRINNING_FACE
    raw = raw * 2730 + "买买买买"
    return {
        "platform": "交" * 128,
        "note": GRINNING_FACE * 2048,
        "raw_text": raw,
    }


def edge_trades() -> list[StoredTrade]:
    """Trades at the edges of what the check accepts; none of them is a sale."""
    coins = edge_coins()
    return [
        saved(
            "edge-big-quantity",
            TradeDraft(
                side=Side.BUY,
                coin="BTC",
                quantity=number("12345678901234567890.123456789012345678"),
                price=number("1.5"),
                fee=number("0"),
                occurred=day(2026, 9, 30),
                raw_text="the largest quantity there is room for",
            ),
        ),
        saved(
            "edge-big-price",
            TradeDraft(
                side=Side.BUY,
                coin="BNB",
                quantity=number("0.000000000000000001"),
                price=number("99999999999999999999.999999999999999999"),
                fee=number("0"),
                occurred=day(2026, 9, 30),
                raw_text="the largest price there is room for",
            ),
        ),
        saved(
            "edge-smallest-amounts",
            TradeDraft(
                side=Side.BUY,
                coin="ETH",
                quantity=number("0.000000000000000001"),
                price=number("123456789"),
                fee=number("0.000000000000000001"),
                fee_coin="USDT",
                occurred=wall(BUDAPEST, (2026, 9, 30, 12, 0)),
                raw_text="the smallest quantity and fee there are",
            ),
        ),
        saved(
            "edge-fee-just-below-quantity",
            TradeDraft(
                side=Side.BUY,
                coin="SOL",
                quantity=number("0.000000000000000002"),
                price=number("94900"),
                fee=number("0.000000000000000001"),
                fee_coin="SOL",
                occurred=wall(BUDAPEST, (2026, 9, 30, 12, 1)),
                raw_text="a fee in the coin bought, just below the quantity",
            ),
        ),
        saved(
            "edge-padded-platform",
            TradeDraft(
                side=Side.BUY,
                coin="newcoin",
                quantity=number("1000"),
                price=number("0.0001234"),
                fee=number("0"),
                occurred=wall("UTC", (2026, 9, 30, 8, 0), 5),
                platform="\N{IDEOGRAPHIC SPACE} Binance \t",
                raw_text="买了 1000 个 newcoin，0.0001234 一个，平台前后带空白",
            ),
            coins,
        ),
        saved(
            "x" * 128,
            TradeDraft(
                side=Side.BUY,
                coin=LONGEST_SYMBOL,
                quantity=number("1"),
                price=number("1"),
                fee=number("0.5"),
                fee_coin=LONGEST_SYMBOL,
                occurred=wall("Asia/Kathmandu", (2026, 9, 30, 10, 15)),
                **_longest_texts(),
            ),
            coins,
        ),
        saved(
            "edge-three-amounts-given",
            TradeDraft(
                side=Side.BUY,
                coin="LINK",
                quantity=number("3"),
                price=number("33.333"),
                total=number("100"),
                fee=number("0.1"),
                fee_coin="USDT",
                occurred=day(2026, 9, 29),
                raw_text="3 LINK for 100 USDT at 33.333, fee 0.1 USDT",
            ),
        ),
        saved(
            "edge-price-worked-out",
            TradeDraft(
                side=Side.BUY,
                coin="DOGE",
                quantity=number("3"),
                total=number("100"),
                fee=number("0"),
                occurred=day(2026, 9, 29),
                raw_text="3 DOGE for 100 USDT",
            ),
        ),
        saved(
            "edge-repeated-hour-first",
            TradeDraft(
                side=Side.BUY,
                coin="ADA",
                quantity=number("10"),
                price=number("0.35"),
                fee=number("0"),
                occurred=wall(BUDAPEST, (2025, 10, 26, 2, 30), fold=0),
                raw_text="02:30 the first time, before the clocks went back",
            ),
        ),
        saved(
            "edge-repeated-hour-second",
            TradeDraft(
                side=Side.BUY,
                coin="ADA",
                quantity=number("10"),
                price=number("0.36"),
                fee=number("0"),
                occurred=wall(BUDAPEST, (2025, 10, 26, 2, 30), fold=1),
                raw_text="02:30 the second time, after the clocks went back",
            ),
        ),
        saved(
            "edge-half-hour-zone",
            TradeDraft(
                side=Side.BUY,
                coin="DOT",
                quantity=number("2"),
                price=number("4.2"),
                fee=number("0"),
                occurred=wall("Asia/Kolkata", (2026, 9, 30, 23, 59), 59),
                raw_text="2 DOT at 4.2 at 23:59:59 in Kolkata",
            ),
        ),
    ]


def edge_text() -> str:
    return exported(edge_trades(), edge_coins())


# --- a fee in a third coin --------------------------------------------------


def third_coin_fee_trades() -> list[StoredTrade]:
    return [
        saved(
            "third-coin-fee",
            TradeDraft(
                side=Side.BUY,
                coin="ETH",
                quantity=number("0.5"),
                price=number("2500"),
                fee=number("0.001"),
                fee_coin="BNB",
                occurred=wall(BUDAPEST, (2026, 10, 3, 18, 0)),
                raw_text="买了 0.5 个 ETH，2500，手续费 0.001 BNB",
            ),
        )
    ]


def third_coin_fee_text() -> str:
    return exported(third_coin_fee_trades())


# --- a sale alone -----------------------------------------------------------


def sell_only_trades() -> list[StoredTrade]:
    return [
        saved(
            "sell-only",
            TradeDraft(
                side=Side.SELL,
                coin="SOL",
                quantity=number("2"),
                price=number("150"),
                fee=number("0.3"),
                fee_coin="USDT",
                occurred=wall(BUDAPEST, (2026, 10, 3, 18, 30)),
                raw_text="卖了 2 个 SOL，150，手续费 0.3 U",
            ),
        )
    ]


def sell_only_text() -> str:
    return exported(sell_only_trades())


# --- planted mistakes -------------------------------------------------------


def _with_change(text: str, change: Callable[[dict[str, object]], None]) -> str:
    document = json.loads(text)
    change(document["ledgerData"])
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _trade(data: dict[str, object], index: int) -> dict[str, object]:
    trades = data["trades"]
    assert isinstance(trades, list)
    entry = trades[index]
    assert isinstance(entry, dict)
    return entry


def broken_texts() -> dict[str, str]:
    """Copies of the golden text, each with one mistake, by the name of the mistake.

    In the golden text the first trade is the XMR buy in Shanghai, the third
    the BTC buy in Budapest.
    """
    golden = golden_text()

    def total_off(data: dict[str, object]) -> None:
        _trade(data, 0)["totalValue"] = "482.5"

    def fee_coin_missing(data: dict[str, object]) -> None:
        _trade(data, 0)["feeCurrency"] = "BNB"

    def zone_disagrees(data: dict[str, object]) -> None:
        _trade(data, 2)["occurredTimeZone"] = SHANGHAI

    return {
        "total-off": _with_change(golden, total_off),
        "fee-coin-missing": _with_change(golden, fee_coin_missing),
        "zone-disagrees": _with_change(golden, zone_disagrees),
    }


# --- every time zone --------------------------------------------------------


def zone_candidates() -> list[str]:
    """Every zone name this machine's zone database lists, and one it loads without listing it."""
    return sorted(available_timezones() | {"posixrules"})


def zones_taken() -> list[str]:
    """The candidates that a trade's time may be recorded in."""
    taken = []
    for name in zone_candidates():
        try:
            OccurredTime(date(2026, 9, 1), TimePrecision.DAY, name)
        except ValueError:
            continue
        taken.append(name)
    return taken


def every_zone_trades() -> list[StoredTrade]:
    """One buy in each zone a trade may be recorded in, all at the same instant."""
    instant = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    return [
        saved(
            f"zone-{place:04d}",
            TradeDraft(
                side=Side.BUY,
                coin="BTC",
                quantity=number("1"),
                price=number("1"),
                fee=number("0"),
                occurred=OccurredTime(
                    instant.astimezone(ZoneInfo(name)), TimePrecision.MINUTE, name
                ),
                raw_text=f"1 BTC at 1 USDT, recorded in {name}",
            ),
        )
        for place, name in enumerate(zones_taken(), start=1)
    ]


def every_zone_text() -> str:
    return exported(every_zone_trades())
