"""Tests of the whole export: the outer fields, the two lists that are filled, refusals, text."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft
from ledger_hand.export.backup import (
    BACKUP_FORMAT_VERSION,
    LEDGER_LIMITS,
    LEDGER_SCHEMA_VERSION,
    ExportIssue,
    ExportLimits,
    ExportProblem,
    ExportRefused,
    export_backup,
)
from tests.export.samples import (
    APP_NAME,
    APP_VERSION,
    EXPORTED_AT,
    TODAY,
    golden_trades,
    saved,
)

BUDAPEST = "Europe/Budapest"


def draft(**changes: Any) -> TradeDraft:
    """A buy that passes every check, with the given fields replaced."""
    fields: dict[str, Any] = {
        "side": Side.BUY,
        "coin": "BTC",
        "quantity": Decimal("0.01"),
        "price": Decimal("95000"),
        "fee": Decimal("0"),
        "occurred": OccurredTime(date(2026, 10, 1), TimePrecision.DAY, BUDAPEST),
        "raw_text": "买了 0.01 BTC，95000",
    }
    fields.update(changes)
    return TradeDraft(**fields)


def trade(identifier: str, coins: CoinTable = BUILT_IN_TABLE, **changes: Any) -> StoredTrade:
    return saved(identifier, draft(**changes), coins)


def minute(day: int, hour: int, minute: int, zone: str = BUDAPEST) -> OccurredTime:
    moment = datetime(2026, 10, day, hour, minute, tzinfo=ZoneInfo(zone))
    return OccurredTime(moment, TimePrecision.MINUTE, zone)


def on(day: int, zone: str = BUDAPEST) -> OccurredTime:
    return OccurredTime(date(2026, 10, day), TimePrecision.DAY, zone)


def export(trades: Iterable[StoredTrade], coins: CoinTable = BUILT_IN_TABLE) -> str | ExportRefused:
    return export_backup(
        trades,
        coins,
        exported_at=EXPORTED_AT,
        today=TODAY,
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )


def document(trades: list[StoredTrade], coins: CoinTable = BUILT_IN_TABLE) -> dict[str, Any]:
    text = export(trades, coins)
    assert isinstance(text, str), text
    parsed = json.loads(text)
    assert isinstance(parsed, dict)
    return parsed


def refusal(
    trades: list[StoredTrade], coins: CoinTable = BUILT_IN_TABLE
) -> tuple[ExportIssue, ...]:
    result = export(trades, coins)
    assert isinstance(result, ExportRefused), result
    return result.issues


# --- the outer fields and the six lists -------------------------------------


def test_the_format_versions_are_those_of_the_ledger_this_program_writes_for() -> None:
    assert BACKUP_FORMAT_VERSION == 3
    assert LEDGER_SCHEMA_VERSION == 5


def test_the_outside_has_the_ledger_s_five_fields_in_its_order() -> None:
    written = document([trade("t1")])

    assert list(written) == [
        "backupFormatVersion",
        "appVersion",
        "exportedAt",
        "ledgerSchemaVersion",
        "ledgerData",
    ]
    assert written["backupFormatVersion"] == 3
    assert written["appVersion"] == "ledger-hand-0.1.0"
    assert written["exportedAt"] == "2026-10-04T08:00:00Z"
    assert written["ledgerSchemaVersion"] == 5


def test_the_ledger_data_has_its_version_and_six_lists_four_of_them_empty() -> None:
    data = document([trade("t1")])["ledgerData"]

    assert list(data) == [
        "schemaVersion",
        "assets",
        "trades",
        "cashEvents",
        "assetTransfers",
        "priceSnapshots",
        "feeRules",
    ]
    assert data["schemaVersion"] == 5
    assert len(data["assets"]) == 1
    assert len(data["trades"]) == 1
    for name in ("cashEvents", "assetTransfers", "priceSnapshots", "feeRules"):
        assert data[name] == []


def test_the_export_moment_is_written_in_utc_to_the_second() -> None:
    moment = datetime(2026, 10, 4, 10, 0, 59, 900_000, tzinfo=ZoneInfo(BUDAPEST))

    text = export_backup(
        [trade("t1")],
        BUILT_IN_TABLE,
        exported_at=moment,
        today=TODAY,
        app_name="a",
        app_version="1",
    )

    assert isinstance(text, str)
    assert json.loads(text)["exportedAt"] == "2026-10-04T08:00:59Z"


# --- which coins get a card -------------------------------------------------


def test_every_coin_traded_and_every_fee_coin_but_usdt_gets_one_card_in_symbol_order() -> None:
    trades = [
        trade("t1", coin="SOL", fee=Decimal("0.01"), fee_coin="BNB"),
        trade("t2", coin="BTC", fee=Decimal("1"), fee_coin="USDT"),
        trade("t3", coin="SOL", fee=Decimal("0.001"), fee_coin="SOL"),
        trade("t4", coin="ETH", fee=Decimal("0")),
        trade("t5", coin="BTC", fee=Decimal("0.0001"), fee_coin="BNB"),
    ]

    assets = document(trades)["ledgerData"]["assets"]

    assert [card["symbol"] for card in assets] == ["BNB", "BTC", "ETH", "SOL"]
    assert [card["id"] for card in assets] == [
        "asset-hand-bnb",
        "asset-hand-btc",
        "asset-hand-eth",
        "asset-hand-sol",
    ]


def test_a_coin_the_user_confirmed_gets_a_card_with_its_symbol_as_name() -> None:
    coins = BUILT_IN_TABLE.with_confirmed("newcoin")

    (card,) = document([trade("t1", coins, coin="newcoin")], coins)["ledgerData"]["assets"]

    assert card["name"] == "NEWCOIN"
    assert card["binanceMapping"] is None


# --- the order of the trades ------------------------------------------------


def test_trades_come_in_the_order_they_happened() -> None:
    trades = [
        trade("a", occurred=minute(3, 12, 0)),
        trade("b", occurred=minute(1, 9, 0)),
        trade("c", occurred=minute(2, 23, 59)),
    ]

    written = document(trades)["ledgerData"]["trades"]

    assert [entry["id"] for entry in written] == ["b", "c", "a"]


def test_a_trade_known_only_to_the_day_comes_at_the_start_of_that_day_in_its_own_zone() -> None:
    # Midnight of 3 October is 2 October 22:00 in UTC for Budapest, and
    # 2 October 16:00 in UTC for Shanghai.
    trades = [
        trade("budapest-day", occurred=on(3)),
        trade("shanghai-day", occurred=on(3, "Asia/Shanghai")),
        trade("budapest-just-after-midnight", occurred=minute(3, 0, 1)),
        trade("budapest-evening-before", occurred=minute(2, 23, 0)),
    ]

    written = document(trades)["ledgerData"]["trades"]

    assert [entry["id"] for entry in written] == [
        "shanghai-day",
        "budapest-evening-before",
        "budapest-day",
        "budapest-just-after-midnight",
    ]


def test_trades_at_the_same_instant_come_in_the_order_of_their_identifiers() -> None:
    same = minute(2, 10, 0)
    # 16:00 in Shanghai is the same instant as 10:00 in Budapest that day.
    trades = [
        trade("m", occurred=same),
        trade("b", occurred=minute(2, 16, 0, "Asia/Shanghai")),
        trade("k", occurred=same),
    ]

    written = document(trades)["ledgerData"]["trades"]

    assert [entry["id"] for entry in written] == ["b", "k", "m"]


# --- the same input, the same bytes -----------------------------------------


def test_the_same_trades_in_any_order_give_the_same_bytes() -> None:
    trades = golden_trades()
    first = export(trades)
    assert isinstance(first, str)

    for order in (list(reversed(trades)), trades[2:] + trades[:2], trades[1::2] + trades[::2]):
        again = export(order)
        assert isinstance(again, str)
        assert again.encode("utf-8") == first.encode("utf-8")


def test_a_generator_of_trades_gives_the_same_bytes_as_a_list() -> None:
    trades = golden_trades()

    assert export(trade for trade in trades) == export(trades)


def test_an_empty_generator_means_no_file() -> None:
    nothing: list[StoredTrade] = []

    assert export(trade for trade in nothing) == ExportRefused(
        (ExportIssue(ExportProblem.NO_TRADES, ""),)
    )


def test_exporting_does_not_change_the_list_it_was_given() -> None:
    trades = golden_trades()
    before = list(trades)

    export(trades)

    assert trades == before


# --- refusals ---------------------------------------------------------------


def test_no_trades_means_no_file() -> None:
    assert refusal([]) == (ExportIssue(ExportProblem.NO_TRADES, ""),)


def test_two_trades_with_one_identifier_are_refused() -> None:
    trades = [trade("same"), trade("other"), trade("same", occurred=on(2))]

    assert refusal(trades) == (ExportIssue(ExportProblem.ID_USED_TWICE, "same"),)


def test_a_trade_may_not_use_the_identifier_of_a_coin_card() -> None:
    trades = [trade("asset-hand-eth", coin="ETH")]

    assert refusal(trades) == (ExportIssue(ExportProblem.ID_USED_TWICE, "asset-hand-eth"),)


def test_a_trade_may_not_use_the_identifier_of_a_fee_coin_s_card() -> None:
    trades = [
        trade("asset-hand-bnb", coin="ETH", fee=Decimal("0.001"), fee_coin="BNB"),
    ]

    assert refusal(trades) == (ExportIssue(ExportProblem.ID_USED_TWICE, "asset-hand-bnb"),)


def test_identifiers_that_are_one_identifier_to_the_ledger_are_used_twice() -> None:
    # A face held as one character, and as its two halves: different texts
    # in Python, one and the same identifier once the ledger reads the file.
    whole = "t-\N{GRINNING FACE}"
    halves = "t-\ud83d\ude00"
    assert whole != halves

    assert refusal([trade(whole), trade(halves, occurred=on(2))]) == (
        ExportIssue(ExportProblem.ID_USED_TWICE, halves),
        ExportIssue(ExportProblem.ID_USED_TWICE, whole),
    )


def test_identifiers_that_differ_in_utf16_are_different() -> None:
    trades = [trade("t-\ud83d"), trade("t-\ude00", occurred=on(2)), trade("t-x", occurred=on(3))]

    assert isinstance(export(trades), str)


def test_the_identifier_of_a_coin_that_is_not_in_the_file_is_free_to_use() -> None:
    trades = [trade("asset-hand-eth", coin="BTC"), trade("asset-hand-usdt", coin="BTC")]

    assert isinstance(export(trades), str)


def test_an_identifier_as_long_as_the_ledger_allows_is_taken() -> None:
    assert isinstance(export([trade("x" * 128)]), str)
    # A face counts as two, as the ledger counts it.
    assert isinstance(export([trade("\N{GRINNING FACE}" * 64)]), str)


@pytest.mark.parametrize("identifier", ["x" * 129, "\N{GRINNING FACE}" * 64 + "x"])
def test_an_identifier_longer_than_the_ledger_allows_is_refused(identifier: str) -> None:
    assert refusal([trade(identifier)]) == (ExportIssue(ExportProblem.ID_TOO_LONG, identifier),)


@pytest.mark.parametrize(
    "identifier", ["", " t1", "t1 ", "\tt1", "t1\N{IDEOGRAPHIC SPACE}", "\N{NO-BREAK SPACE}t1"]
)
def test_an_empty_or_padded_identifier_is_refused(identifier: str) -> None:
    assert refusal([trade(identifier)]) == (
        ExportIssue(ExportProblem.ID_EMPTY_OR_PADDED, identifier),
    )


def test_a_coin_missing_from_the_table_is_refused_whether_traded_or_paid_as_a_fee() -> None:
    coins = BUILT_IN_TABLE.with_confirmed("newcoin").with_confirmed("feecoin")
    trades = [
        trade("t1", coins, coin="newcoin"),
        trade("t2", coins, coin="BTC", fee=Decimal("1"), fee_coin="feecoin"),
    ]

    assert refusal(trades, BUILT_IN_TABLE) == (
        ExportIssue(ExportProblem.COIN_NOT_IN_TABLE, "FEECOIN"),
        ExportIssue(ExportProblem.COIN_NOT_IN_TABLE, "NEWCOIN"),
    )


def test_every_issue_is_listed_at_once_in_a_fixed_order() -> None:
    coins = BUILT_IN_TABLE.with_confirmed("newcoin")
    trades = [
        trade("dup"),
        trade("dup", occurred=on(2)),
        trade("y" * 200),
        trade(" padded"),
        trade("asset-hand-btc"),
        trade("t-new", coins, coin="newcoin"),
    ]

    assert refusal(trades) == (
        ExportIssue(ExportProblem.ID_EMPTY_OR_PADDED, " padded"),
        ExportIssue(ExportProblem.ID_TOO_LONG, "y" * 200),
        ExportIssue(ExportProblem.ID_USED_TWICE, "asset-hand-btc"),
        ExportIssue(ExportProblem.ID_USED_TWICE, "dup"),
        ExportIssue(ExportProblem.COIN_NOT_IN_TABLE, "NEWCOIN"),
    )


def old_moment(zone: str, year: int, month: int = 6, day: int = 1) -> OccurredTime:
    """Noon on an old day, on the wall clock of ``zone`` as it was then."""
    moment = datetime(year, month, day, 12, 0, tzinfo=ZoneInfo(zone))
    return OccurredTime(moment, TimePrecision.MINUTE, zone)


@pytest.mark.parametrize(
    ("zone", "year", "offset"),
    [
        (BUDAPEST, 1890, "+01:16:20"),
        ("Asia/Shanghai", 1900, "+08:05:43"),
        ("America/New_York", 1880, "-04:56:02"),
    ],
)
def test_a_time_whose_offset_has_seconds_is_refused_not_failed_on(
    zone: str, year: int, offset: str
) -> None:
    occurred = old_moment(zone, year)
    assert occurred.value.isoformat().endswith(offset)
    old = trade("old", occurred=occurred)

    assert refusal([old]) == (ExportIssue(ExportProblem.OFFSET_NOT_WHOLE_MINUTES, "old"),)


def test_only_the_trades_whose_offset_has_seconds_are_named() -> None:
    trades = [
        trade("fine", occurred=minute(2, 10, 0)),
        trade("old-shanghai", occurred=old_moment("Asia/Shanghai", 1900)),
        trade("old-budapest", occurred=old_moment(BUDAPEST, 1890)),
    ]

    assert refusal(trades) == (
        ExportIssue(ExportProblem.OFFSET_NOT_WHOLE_MINUTES, "old-budapest"),
        ExportIssue(ExportProblem.OFFSET_NOT_WHOLE_MINUTES, "old-shanghai"),
    )


def test_an_offset_with_seconds_is_listed_after_the_other_issues() -> None:
    trades = [trade("dup"), trade("dup", occurred=old_moment(BUDAPEST, 1890))]

    assert refusal(trades) == (
        ExportIssue(ExportProblem.ID_USED_TWICE, "dup"),
        ExportIssue(ExportProblem.OFFSET_NOT_WHOLE_MINUTES, "dup"),
    )


def test_old_times_with_whole_minute_offsets_and_old_days_are_exported() -> None:
    trades = [
        trade("budapest-1950", occurred=old_moment(BUDAPEST, 1950)),
        trade("kolkata-1950", occurred=old_moment("Asia/Kolkata", 1950)),
        trade(
            "budapest-1890-day",
            occurred=OccurredTime(date(1890, 6, 1), TimePrecision.DAY, BUDAPEST),
        ),
    ]

    written = {
        entry["id"]: entry["occurredAt"] for entry in document(trades)["ledgerData"]["trades"]
    }

    assert written == {
        "budapest-1890-day": "1890-06-01",
        "budapest-1950": "1950-06-01T12:00:00+01:00",
        "kolkata-1950": "1950-06-01T12:00:00+05:30",
    }


# --- how much one file may hold --------------------------------------------


def export_within(
    trades: list[StoredTrade], limits: ExportLimits, coins: CoinTable = BUILT_IN_TABLE
) -> str | ExportRefused:
    return export_backup(
        trades,
        coins,
        exported_at=EXPORTED_AT,
        today=TODAY,
        app_name=APP_NAME,
        app_version=APP_VERSION,
        limits=limits,
    )


def test_the_limits_are_the_ledger_s_unless_lower_ones_are_handed_in() -> None:
    assert ExportLimits(max_coins=500, max_trades=250_000, max_bytes=134_217_728) == LEDGER_LIMITS


@pytest.mark.parametrize(
    "changes",
    [
        {"max_coins": 501},
        {"max_trades": 250_001},
        {"max_bytes": 134_217_729},
        {"max_coins": 0},
        {"max_trades": -1},
        {"max_bytes": True},
        {"max_coins": 2.0},
    ],
)
def test_a_limit_above_the_ledger_s_or_not_a_positive_whole_number_is_refused(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="must be a whole number from 1 to"):
        ExportLimits(**changes)  # type: ignore[arg-type]


def test_as_many_coins_as_the_limit_are_exported_and_one_more_is_refused() -> None:
    trades = [
        trade("t1", coin="BTC"),
        trade("t2", coin="ETH", fee=Decimal("0.01"), fee_coin="BNB"),
    ]

    assert isinstance(export_within(trades, ExportLimits(max_coins=3)), str)
    assert export_within(trades, ExportLimits(max_coins=2)) == ExportRefused(
        (ExportIssue(ExportProblem.TOO_MANY_COINS, "3"),)
    )


def test_as_many_trades_as_the_limit_are_exported_and_one_more_is_refused() -> None:
    trades = [trade("t1"), trade("t2"), trade("t3")]

    assert isinstance(export_within(trades, ExportLimits(max_trades=3)), str)
    assert export_within(trades, ExportLimits(max_trades=2)) == ExportRefused(
        (ExportIssue(ExportProblem.TOO_MANY_TRADES, "3"),)
    )


def test_a_file_as_large_as_the_limit_is_exported_and_one_byte_more_is_refused() -> None:
    trades = [trade("t1", raw_text="买了 0.01 BTC \N{GRINNING FACE}，95000", note="Ä")]
    text = export_within(trades, LEDGER_LIMITS)
    assert isinstance(text, str)
    size = len(text.encode("utf-8"))
    assert size > len(text)

    assert export_within(trades, ExportLimits(max_bytes=size)) == text
    assert export_within(trades, ExportLimits(max_bytes=size - 1)) == ExportRefused(
        (ExportIssue(ExportProblem.FILE_TOO_LARGE, str(size)),)
    )


def test_the_size_is_looked_at_only_when_nothing_else_stands_in_the_way() -> None:
    trades = [trade("dup"), trade("dup", occurred=on(2))]

    assert export_within(trades, ExportLimits(max_bytes=1, max_trades=1)) == ExportRefused(
        (
            ExportIssue(ExportProblem.ID_USED_TWICE, "dup"),
            ExportIssue(ExportProblem.TOO_MANY_TRADES, "2"),
        )
    )


def test_one_coin_more_than_the_ledger_holds_is_refused_with_the_ledger_s_own_limit() -> None:
    coins = BUILT_IN_TABLE
    for number in range(501):
        coins = coins.with_confirmed(f"COIN{number}")
    trades = [trade(f"t{number}", coins, coin=f"COIN{number}") for number in range(501)]

    assert export_within(trades, LEDGER_LIMITS, coins) == ExportRefused(
        (ExportIssue(ExportProblem.TOO_MANY_COINS, "501"),)
    )
    assert isinstance(export_within(trades[:500], LEDGER_LIMITS, coins), str)


# --- today -------------------------------------------------------------------

LATER_NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def later(identifier: str, occurred: OccurredTime) -> StoredTrade:
    """A trade the check accepted when it was already 6 October everywhere."""
    return saved(identifier, draft(occurred=occurred), now=LATER_NOW)


def at(zone: str, moment: datetime) -> OccurredTime:
    return OccurredTime(moment.astimezone(ZoneInfo(zone)), TimePrecision.MINUTE, zone)


def export_on(trades: list[StoredTrade], today: date) -> str | ExportRefused:
    return export_backup(
        trades,
        BUILT_IN_TABLE,
        exported_at=EXPORTED_AT,
        today=today,
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )


def test_a_trade_dated_today_or_before_is_exported() -> None:
    trades = [later("today", on(4)), later("yesterday", on(3))]

    assert isinstance(export_on(trades, date(2026, 10, 4)), str)


def test_a_trade_dated_after_today_in_its_own_zone_is_refused_and_named() -> None:
    # One instant: still 4 October in Budapest, already 5 October in Tokyo
    # and in Kiritimati, still 4 October in Los Angeles.
    instant = datetime(2026, 10, 4, 21, 30, tzinfo=timezone.utc)
    trades = [
        later("budapest", at(BUDAPEST, instant)),
        later("tokyo", at("Asia/Tokyo", instant)),
        later("kiritimati", at("Pacific/Kiritimati", instant)),
        later("los-angeles", at("America/Los_Angeles", instant)),
        later("tomorrow-day", on(5)),
    ]

    assert export_on(trades, date(2026, 10, 4)) == ExportRefused(
        (
            ExportIssue(ExportProblem.DATED_AFTER_TODAY, "kiritimati"),
            ExportIssue(ExportProblem.DATED_AFTER_TODAY, "tokyo"),
            ExportIssue(ExportProblem.DATED_AFTER_TODAY, "tomorrow-day"),
        )
    )
    assert isinstance(export_on(trades, date(2026, 10, 5)), str)


def test_the_date_compared_is_the_one_written_in_the_file() -> None:
    instant = datetime(2026, 10, 4, 21, 30, tzinfo=timezone.utc)
    trade = later("tokyo", at("Asia/Tokyo", instant))

    text = export_on([trade], date(2026, 10, 5))

    assert isinstance(text, str)
    assert json.loads(text)["ledgerData"]["trades"][0]["occurredAt"].startswith("2026-10-05")


@pytest.mark.parametrize(
    "today", [datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc), "2026-10-04", None]
)
def test_today_must_be_a_plain_date(today: object) -> None:
    with pytest.raises(TypeError, match="today must be a date"):
        export_on([trade("t1")], today)  # type: ignore[arg-type]


# --- mistakes of the calling code -------------------------------------------


def test_an_export_moment_without_an_offset_is_a_mistake_of_the_caller() -> None:
    with pytest.raises(ValueError, match="needs a time zone offset"):
        export_backup(
            [trade("t1")],
            BUILT_IN_TABLE,
            exported_at=datetime(2026, 10, 4, 8, 0),
            today=TODAY,
            app_name=APP_NAME,
            app_version=APP_VERSION,
        )


@pytest.mark.parametrize(
    ("name", "version"),
    [("", "0.1.0"), ("ledger-hand", ""), (" ledger-hand", "0.1.0"), ("ledger-hand", "0.1.0\n")],
)
def test_a_program_name_or_version_the_ledger_would_refuse_is_a_mistake_of_the_caller(
    name: str, version: str
) -> None:
    with pytest.raises(ValueError, match="trimmed text"):
        export_backup(
            [trade("t1")],
            BUILT_IN_TABLE,
            exported_at=EXPORTED_AT,
            today=TODAY,
            app_name=name,
            app_version=version,
        )


def test_a_program_name_and_version_longer_than_the_ledger_allows_is_refused() -> None:
    assert isinstance(
        export_backup(
            [trade("t1")],
            BUILT_IN_TABLE,
            exported_at=EXPORTED_AT,
            today=TODAY,
            app_name="n" * 126,
            app_version="1",
        ),
        str,
    )
    with pytest.raises(ValueError, match="longer than the ledger allows"):
        export_backup(
            [trade("t1")],
            BUILT_IN_TABLE,
            exported_at=EXPORTED_AT,
            today=TODAY,
            app_name="n" * 127,
            app_version="1",
        )


# --- the text ---------------------------------------------------------------


def test_the_text_is_indented_by_two_spaces_and_ends_with_one_line_break() -> None:
    text = export([trade("t1")])
    assert isinstance(text, str)

    assert text.startswith('{\n  "backupFormatVersion": 3,\n  "appVersion": "ledger-hand-0.1.0",\n')
    assert text.endswith("\n  }\n}\n")
    assert not text.endswith("\n\n")


def test_letters_of_every_language_are_written_as_they_are() -> None:
    text = export([trade("t1", raw_text="买了 0.01 BTC \N{GRINNING FACE}", note="Ä é ж")])
    assert isinstance(text, str)

    assert '"rawText": "买了 0.01 BTC \N{GRINNING FACE}"' in text
    assert '"note": "Ä é ж"' in text
    assert "\\u" not in text


def test_control_characters_and_quotes_are_escaped() -> None:
    raw = 'line one\nline "two"\tend\\'
    text = export([trade("t1", raw_text=raw)])
    assert isinstance(text, str)

    assert '"rawText": "line one\\nline \\"two\\"\\tend\\\\"' in text
    assert json.loads(text)["ledgerData"]["trades"][0]["rawText"] == raw


def test_a_lone_half_of_a_surrogate_pair_is_escaped_so_the_text_is_valid_utf8() -> None:
    raw = "broken \ud83d text"
    text = export([trade("t1", raw_text=raw)])
    assert isinstance(text, str)

    assert '"rawText": "broken \\ud83d text"' in text
    text.encode("utf-8")
    assert json.loads(text)["ledgerData"]["trades"][0]["rawText"] == raw


def test_the_text_reads_back_as_the_entries_that_went_in() -> None:
    written = document([trade("t1", platform="Binance", note="n")])

    (entry,) = written["ledgerData"]["trades"]
    assert entry["id"] == "t1"
    assert entry["quantity"] == "0.01"
    assert entry["totalValue"] == "950"
    assert entry["platform"] == "Binance"
    assert entry["note"] == "n"
    assert entry["createdAt"] == datetime(2026, 10, 4, 7, 41, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
