"""The golden sample: a committed export file that the export must reproduce byte for byte.

The file is never edited after it is committed: it is the record of what this
version of the format looks like. A change to the export that changes its
bytes is a change of format; it raises a version number and adds a golden
sample of its own, beside this one. The hash below makes an edit of the file
fail even when the export was changed to match it.

Whether the ledger itself accepts the file is checked by the ledger tier
(``scripts/check.sh ledger``).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ledger_hand.export.backup import BACKUP_FORMAT_VERSION, LEDGER_SCHEMA_VERSION
from tests.export.samples import GOLDEN_FILE, golden_text

GOLDEN_SHA256 = "fb859461dfb6d14448872b96f679dd9311dc9d738022e700166e6309533bcd03"

_CHINESE = re.compile("[一-鿿]")


def golden() -> dict[str, Any]:
    document = json.loads(GOLDEN_FILE.read_bytes().decode("utf-8"))
    assert isinstance(document, dict)
    return document


def test_the_export_of_the_golden_trades_is_the_golden_sample_byte_for_byte() -> None:
    assert golden_text().encode("utf-8") == GOLDEN_FILE.read_bytes()


def test_the_golden_sample_has_not_been_edited_since_it_was_committed() -> None:
    assert hashlib.sha256(GOLDEN_FILE.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_golden_sample_s_name_carries_both_format_versions() -> None:
    assert GOLDEN_FILE.name == "backup-format-v3-ledger-schema-v5.json"
    assert golden()["backupFormatVersion"] == BACKUP_FORMAT_VERSION == 3
    assert golden()["ledgerSchemaVersion"] == LEDGER_SCHEMA_VERSION == 5


def test_the_golden_sample_covers_what_it_is_meant_to_cover() -> None:
    data = golden()["ledgerData"]
    trades = data["trades"]
    symbols = {trade["assetSymbol"] for trade in trades}

    # Buys, and a sale of a coin bought before it in the same file.
    assert {trade["type"] for trade in trades} == {"buy", "sell"}
    for sale in (trade for trade in trades if trade["type"] == "sell"):
        earlier = trades[: trades.index(sale)]
        assert any(t["type"] == "buy" and t["assetSymbol"] == sale["assetSymbol"] for t in earlier)
    # A fee of zero, a fee in USDT, and fees in the coin itself on a buy and on
    # a sale; never a fee in a third coin.
    assert any(trade["fee"] == "0" for trade in trades)
    assert any(trade["fee"] != "0" and trade["feeCurrency"] == "USDT" for trade in trades)
    own_coin_fees = {
        trade["type"]
        for trade in trades
        if trade["fee"] != "0" and trade["feeCurrency"] == trade["assetSymbol"]
    }
    assert own_coin_fees == {"buy", "sell"}
    assert all(trade["feeCurrency"] in {"USDT", trade["assetSymbol"]} for trade in trades)
    # Times known to the day, the minute and the second, in more than one zone.
    assert {trade["timePrecision"] for trade in trades} == {"day", "minute", "second"}
    assert len({trade["occurredTimeZone"] for trade in trades}) > 1
    # Platform and note, each given and not given.
    for field in ("platform", "note"):
        assert {field in trade for trade in trades} == {True, False}
    # An original text in Chinese.
    assert any(_CHINESE.search(trade["rawText"]) for trade in trades)
    # A coin with no market on Binance, and one with a market.
    mappings = {card["symbol"]: card["binanceMapping"] for card in data["assets"]}
    assert set(mappings) == symbols
    assert None in mappings.values()
    assert any(mapping is not None for mapping in mappings.values())
