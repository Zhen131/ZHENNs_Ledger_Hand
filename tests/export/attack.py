"""Batches of edge-case trades made to find where this program and the ledger part ways.

The ledger tier hands each batch to the ledger. The promise being tested:
every trade the check (``validation.check_draft``) accepts is either exported
and then accepted by the ledger, or refused by the export with a reason;
never anything else. So every trade below goes through the real check first,
and every batch is expected to be accepted, except the few made to be refused.

- ``first_days``, ``earliest_moments``: 1 January and 2 January of the year 1,
  in every time zone, to the day, the minute and the second.
- ``last_days``: 31 December 9999 to the day and 30 December 9999 to the
  minute and second, in every zone the check accepts them in; handed to the
  ledger with that last day as its today.
- ``characters``: texts, platforms and identifiers made of every awkward kind
  of character.
- ``numbers``: the largest and smallest amounts, worked-out amounts, fees that
  only just fit.
- ``across_zones``: one instant recorded in zones on both sides of midnight,
  for a today when the day has turned in some of them and not in others;
  ``every_zone_on_the_day``: that instant in every zone.
- ``full_run``: buys followed by sales, selling everything that was bought,
  with the other edges mixed in, so that the ledger runs every one of its
  checks on it.
- ``coins_at_limit``, ``file_at_size``, ``too_many_trades``: the ledger's limits
  of one file, at the limit and one past it.

Each function returns the trades; the coin table and today they need, where
they are not the usual ones, come from the function next to it.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.ledger_limits import (
    MAX_COINS_PER_FILE,
    MAX_TRADES_PER_FILE,
    RAW_TEXT_MAX_LENGTH,
    text_length,
)
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import check_draft
from tests.export.samples import BUDAPEST, CREATED, NOW, saved, zones_taken

GRINNING_FACE = "\N{GRINNING FACE}"
FAMILY = (
    "\N{MAN}\N{ZERO WIDTH JOINER}\N{WOMAN}\N{ZERO WIDTH JOINER}\N{GIRL}\N{ZERO WIDTH JOINER}\N{BOY}"
)
FLAGS = (
    "\N{REGIONAL INDICATOR SYMBOL LETTER H}\N{REGIONAL INDICATOR SYMBOL LETTER U}"
    "\N{REGIONAL INDICATOR SYMBOL LETTER C}\N{REGIONAL INDICATOR SYMBOL LETTER N}"
)
# Every kind of character a text could hold that a writer of JSON, a reader of
# JSON or a counter of length might trip over.
AWKWARD = (
    f"{GRINNING_FACE}{FAMILY}{FLAGS}"
    "e\N{COMBINING ACUTE ACCENT} \U00020000 \N{ARABIC LETTER MEEM}\N{ARABIC LETTER REH}"
    ' "quoted" \\back\\slash </script> '
    "\r\n\t\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}\x00\x01\x1f\x7f"
    "\N{ZERO WIDTH NO-BREAK SPACE}\N{ZERO WIDTH JOINER}\N{RIGHT-TO-LEFT MARK}"
    "\N{REPLACEMENT CHARACTER}\ud83d"
)

# The current moments of the check for the batches that need a later one.
LATE_NOW = datetime(9999, 12, 31, 9, 59, tzinfo=timezone.utc)
LAST_TODAY = date(9999, 12, 31)
ACROSS_NOW = datetime(2026, 10, 5, 6, 46, tzinfo=timezone.utc)
ACROSS_TODAY = date(2026, 10, 5)


def _buy(occurred: OccurredTime, **changes: object) -> TradeDraft:
    draft = TradeDraft(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("1"),
        price=Decimal("1"),
        fee=Decimal("0"),
        occurred=occurred,
        raw_text=f"1 BTC at 1 USDT, {occurred.value} in {occurred.time_zone}",
    )
    return dataclasses.replace(draft, **changes)  # type: ignore[arg-type]


def _taken(identifier: str, draft: TradeDraft, now: datetime) -> StoredTrade | None:
    """``draft`` saved if the check accepts it at ``now``; ``None`` if it does not."""
    result = check_draft(draft, BUILT_IN_TABLE, now)
    if not isinstance(result, TradeRecord):
        return None
    return StoredTrade(id=identifier, record=result, created_at=CREATED, updated_at=CREATED)


def _cut_to_length(text: str, length: int) -> str:
    """The longest start of ``text`` no longer than ``length`` as the ledger counts it."""
    cut = []
    used = 0
    for character in text:
        size = text_length(character)
        if used + size > length:
            break
        cut.append(character)
        used += size
    return "".join(cut)


def _whole_minute_offset(moment: datetime) -> bool:
    offset = moment.utcoffset()
    return offset is not None and not offset.total_seconds() % 60


# --- the two ends of time ---------------------------------------------------


def first_days() -> list[StoredTrade]:
    """1 January of the year 1, to the day, in every zone."""
    trades = []
    for place, zone in enumerate(zones_taken()):
        occurred = OccurredTime(date(1, 1, 1), TimePrecision.DAY, zone)
        trade = _taken(f"first-day-{place:04d}", _buy(occurred), NOW)
        assert trade is not None, zone
        trades.append(trade)
    return trades


def earliest_moments() -> list[StoredTrade]:
    """Noon of 2 January of the year 1, to the minute and to the second, in every zone.

    Only the zones whose offset was then a whole number of minutes: the others
    are refused by the export, which the tests of the export show.
    """
    trades = []
    for place, zone in enumerate(zones_taken()):
        for second, precision in ((0, TimePrecision.MINUTE), (1, TimePrecision.SECOND)):
            local = datetime(1, 1, 2, 12, 0, second, tzinfo=ZoneInfo(zone))
            if not _whole_minute_offset(local):
                continue
            occurred = OccurredTime(local, precision, zone)
            trade = _taken(f"earliest-{place:04d}-{precision.value}", _buy(occurred), NOW)
            assert trade is not None, zone
            trades.append(trade)
    return trades


def last_days() -> list[StoredTrade]:
    """31 December 9999 to the day, and 30 December 9999 to the minute and second."""
    trades = []
    for place, zone in enumerate(zones_taken()):
        day = OccurredTime(date(9999, 12, 31), TimePrecision.DAY, zone)
        trade = _taken(f"last-day-{place:04d}", _buy(day), LATE_NOW)
        if trade is not None:
            trades.append(trade)
        for second, precision in ((0, TimePrecision.MINUTE), (59, TimePrecision.SECOND)):
            local = datetime(9999, 12, 30, 12, 0, second, tzinfo=ZoneInfo(zone))
            occurred = OccurredTime(local, precision, zone)
            trade = _taken(f"latest-{place:04d}-{precision.value}", _buy(occurred), LATE_NOW)
            assert trade is not None, zone
            trades.append(trade)
    return trades


# --- characters -------------------------------------------------------------


def characters_coins() -> CoinTable:
    return BUILT_IN_TABLE.with_confirmed("newtoken2026").with_confirmed("1000")


def characters() -> list[StoredTrade]:
    """Awkward characters in every free text, and in identifiers."""
    coins = characters_coins()
    on_day = OccurredTime(date(2026, 9, 20), TimePrecision.DAY, BUDAPEST)
    repeated = AWKWARD * (RAW_TEXT_MAX_LENGTH // len(AWKWARD) + 1)
    long_raw = _cut_to_length(repeated, RAW_TEXT_MAX_LENGTH - 2)
    padded_platform = (
        f"\N{IDEOGRAPHIC SPACE}\N{ZERO WIDTH NO-BREAK SPACE}\t{FAMILY} Ex  change\N{NO-BREAK SPACE}"
    )
    longest_id = "\N{CJK UNIFIED IDEOGRAPH-4E70}" * 120 + GRINNING_FACE * 4
    drafts = {
        "awkward-raw-text": _buy(on_day, raw_text=AWKWARD),
        "awkward-note": _buy(on_day, note=AWKWARD, raw_text="note"),
        "awkward-platform": _buy(
            on_day,
            platform=padded_platform,
            raw_text="platform",
        ),
        "awkward-long": _buy(on_day, raw_text=long_raw + GRINNING_FACE),
        f"id {FAMILY} \N{CJK UNIFIED IDEOGRAPH-4E70}": _buy(on_day, raw_text="identifier"),
        "id-with-\x00-inside": _buy(on_day, raw_text="identifier with a null"),
        "id-with-half-\ud83d": _buy(on_day, raw_text="identifier with half a face"),
        longest_id: _buy(on_day, raw_text="longest"),
        "confirmed-coin-letters": _buy(on_day, coin="newtoken2026", raw_text="NEWTOKEN2026"),
        "confirmed-coin-digits": _buy(on_day, coin="1000", raw_text="1000"),
    }
    return [saved(identifier, draft, coins) for identifier, draft in drafts.items()]


# --- numbers ----------------------------------------------------------------


def numbers_coins() -> CoinTable:
    return BUILT_IN_TABLE.with_confirmed("feecoin")


def numbers() -> list[StoredTrade]:
    """The largest and smallest amounts, amounts the program works out, fees that just fit."""
    coins = numbers_coins()
    on_day = OccurredTime(date(2026, 9, 21), TimePrecision.DAY, BUDAPEST)
    tiny = Decimal("0.000000000000000001")

    def amounts(**fields: object) -> TradeDraft:
        draft = _buy(on_day, raw_text=f"amounts {sorted(fields)}")
        stated: dict[str, object] = {"quantity": None, "price": None, "total": None}
        stated.update(fields)
        return dataclasses.replace(draft, **stated)  # type: ignore[arg-type]

    drafts = {
        "forty-digit-quantity": amounts(
            quantity=Decimal("1234567890123456789012.123456789012345678"), price=tiny
        ),
        "forty-digit-whole-quantity": amounts(
            quantity=Decimal("1234567890123456789012345678901234567890"), price=tiny
        ),
        "forty-digit-price": amounts(
            quantity=tiny, price=Decimal("1234567890123456789012.123456789012345678")
        ),
        "total-rounded-half-up": amounts(
            quantity=Decimal("0.000000000000000003"), price=Decimal("0.5")
        ),
        "price-worked-out": amounts(quantity=Decimal("3"), total=Decimal("1000")),
        "quantity-worked-out": amounts(price=Decimal("3"), total=Decimal("100")),
        "all-three-a-cent-apart": amounts(
            quantity=Decimal("1"), price=Decimal("100"), total=Decimal("100.01")
        ),
        "fee-in-coin-just-below": dataclasses.replace(
            _buy(on_day, raw_text="fee just below"),
            quantity=Decimal("1.000000000000000001"),
            fee=Decimal("1"),
            fee_coin="BTC",
        ),
        "zero-fee-said-in-btc": dataclasses.replace(
            _buy(on_day, raw_text="zero fee in BTC"), fee=Decimal("0.000"), fee_coin="BTC"
        ),
        "fee-in-a-third-built-in-coin": dataclasses.replace(
            _buy(on_day, raw_text="fee in BNB"), fee=Decimal("0.001"), fee_coin="BNB"
        ),
        "fee-in-a-third-confirmed-coin": dataclasses.replace(
            _buy(on_day, raw_text="fee in FEECOIN"), fee=Decimal("5"), fee_coin="feecoin"
        ),
    }
    return [saved(identifier, draft, coins) for identifier, draft in drafts.items()]


# --- one instant on both sides of midnight ----------------------------------


ACROSS_ZONES = (
    BUDAPEST,
    "Asia/Tokyo",
    "Pacific/Kiritimati",
    "America/Los_Angeles",
    "Etc/GMT+12",
    "UTC",
    "Asia/Kathmandu",
)


def across_zones() -> list[StoredTrade]:
    """An hour before 06:46 UTC on 5 October 2026, recorded in zones on both sides of midnight.

    It is 5 October in some of them and 4 October in others; a day-precision
    trade on 5 October in Kiritimati and on 4 October at UTC-12 is added.
    """
    instant = datetime(2026, 10, 5, 5, 46, tzinfo=timezone.utc)
    trades = []
    for zone in ACROSS_ZONES:
        local = instant.astimezone(ZoneInfo(zone))
        occurred = OccurredTime(local, TimePrecision.MINUTE, zone)
        trade = _taken(f"across-{zone}", _buy(occurred), ACROSS_NOW)
        assert trade is not None, zone
        trades.append(trade)
    for identifier, day, zone in (
        ("across-day-kiritimati", date(2026, 10, 5), "Pacific/Kiritimati"),
        ("across-day-utc-minus-12", date(2026, 10, 4), "Etc/GMT+12"),
    ):
        trade = _taken(identifier, _buy(OccurredTime(day, TimePrecision.DAY, zone)), ACROSS_NOW)
        assert trade is not None, zone
        trades.append(trade)
    return trades


def every_zone_on_the_day() -> list[StoredTrade]:
    """The same instant, an hour before the check's now on 5 October 2026, in every zone."""
    instant = datetime(2026, 10, 5, 5, 46, tzinfo=timezone.utc)
    trades = []
    for place, zone in enumerate(zones_taken()):
        occurred = OccurredTime(instant.astimezone(ZoneInfo(zone)), TimePrecision.MINUTE, zone)
        trade = _taken(f"on-the-day-{place:04d}", _buy(occurred), ACROSS_NOW)
        assert trade is not None, zone
        trades.append(trade)
    return trades


# --- buys followed by sales -------------------------------------------------


def full_run_coins() -> CoinTable:
    return BUILT_IN_TABLE.with_confirmed("newcoin")


def full_run() -> list[StoredTrade]:
    """Buys, then sales of all or part of what was bought, with other edges mixed in.

    Nothing is sold that was not bought before it, so the ledger's holdings
    work out and it goes on to its last checks.
    """
    coins = full_run_coins()
    day = OccurredTime(date(2026, 9, 25), TimePrecision.DAY, BUDAPEST)

    def at(hour: int, minute: int, zone: str = BUDAPEST) -> OccurredTime:
        local = datetime(2026, 9, 25, hour, minute, tzinfo=ZoneInfo(zone))
        return OccurredTime(local, TimePrecision.MINUTE, zone)

    def deal(
        side: Side, coin: str, quantity: str, occurred: OccurredTime, **fee: object
    ) -> TradeDraft:
        draft = _buy(
            occurred,
            side=side,
            coin=coin,
            quantity=Decimal(quantity),
            price=Decimal("100"),
            raw_text=f"{side.value} {quantity} {coin} {AWKWARD}",
        )
        return dataclasses.replace(draft, **fee)  # type: ignore[arg-type]

    def fee_in(amount: str, coin: str) -> dict[str, object]:
        return {"fee": Decimal(amount), "fee_coin": coin}

    drafts = [
        # Bought to the day, sold later that day to the minute: the day comes first.
        ("eth-buy", deal(Side.BUY, "ETH", "2.1", day)),
        ("eth-sell-all", deal(Side.SELL, "ETH", "2", at(18, 0), **fee_in("0.1", "ETH"))),
        # A buy fee in the coin itself, then a sale of exactly what was left.
        ("sol-buy", deal(Side.BUY, "SOL", "1", at(9, 0), **fee_in("0.01", "SOL"))),
        ("sol-sell-rest", deal(Side.SELL, "SOL", "0.99", at(9, 30))),
        # A sale with its fee in a third coin, partly.
        ("btc-buy", deal(Side.BUY, "BTC", "0.5", at(10, 0, "Asia/Tokyo"))),
        ("btc-sell", deal(Side.SELL, "BTC", "0.2", at(11, 0), **fee_in("0.001", "BNB"))),
        # A coin the user confirmed, bought and sold to the day.
        ("new-buy", deal(Side.BUY, "newcoin", "1000", day)),
        ("new-sell", deal(Side.SELL, "newcoin", "999.999999999999999999", day, **fee_in("1", "U"))),
    ]
    return [saved(identifier, draft, coins) for identifier, draft in drafts]


# --- the ledger's limits of one file ----------------------------------------


def coins_at_limit_coins(count: int = MAX_COINS_PER_FILE) -> CoinTable:
    coins = BUILT_IN_TABLE
    for number in range(count):
        coins = coins.with_confirmed(f"LIM{number:04d}")
    return coins


def coins_at_limit(count: int = MAX_COINS_PER_FILE) -> list[StoredTrade]:
    """One buy of each of ``count`` coins the user confirmed."""
    coins = coins_at_limit_coins(count)
    on_day = OccurredTime(date(2026, 9, 22), TimePrecision.DAY, BUDAPEST)
    return [
        saved(f"lim-{number:04d}", _buy(on_day, coin=f"LIM{number:04d}"), coins)
        for number in range(count)
    ]


def with_one_more_coin_card(text: str) -> str:
    """``text`` with one more coin card, used by no trade, at the end of the coins."""
    document = json.loads(text)
    assets = document["ledgerData"]["assets"]
    extra = dict(assets[-1], id="asset-hand-unused", symbol="UNUSED", name="UNUSED")
    assets.append(extra)
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def too_many_trades(count: int = MAX_TRADES_PER_FILE + 1) -> list[StoredTrade]:
    """``count`` buys, all one record under different identifiers, to be quick to build."""
    record = saved("t", _buy(OccurredTime(date(2026, 9, 23), TimePrecision.DAY, BUDAPEST))).record
    return [
        StoredTrade(id=f"many-{number:06d}", record=record, created_at=CREATED, updated_at=CREATED)
        for number in range(count)
    ]


def file_trades(size: int, measure: Callable[[list[StoredTrade]], int]) -> list[StoredTrade]:
    """Trades whose export is exactly ``size`` bytes long.

    ``measure`` is a function from trades to the size of their export. Full
    trades carry the longest original text there is, of plain letters, one
    byte each; one last trade takes up the rest in its original text and note.
    """
    on_day = OccurredTime(date(2026, 9, 24), TimePrecision.DAY, BUDAPEST)
    full = saved("t", _buy(on_day, raw_text="a" * RAW_TEXT_MAX_LENGTH)).record

    def fulls(count: int) -> list[StoredTrade]:
        return [
            StoredTrade(id=f"big-{number:06d}", record=full, created_at=CREATED, updated_at=CREATED)
            for number in range(count)
        ]

    def tail(extra: int) -> StoredTrade:
        raw = 1 + min(extra, RAW_TEXT_MAX_LENGTH - 1)
        note = 1 + extra - (raw - 1)
        draft = _buy(on_day, raw_text="b" * raw, note="c" * note)
        return saved("big-tail", draft)

    empty = measure([tail(0)])
    step = measure([*fulls(1), tail(0)]) - empty
    count, extra = divmod(size - empty, step)
    trades = [*fulls(count), tail(extra)]
    assert measure(trades) == size
    return trades
