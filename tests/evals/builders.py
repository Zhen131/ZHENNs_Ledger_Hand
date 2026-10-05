"""Small builders for the scoring tests: invented sentences, gold trades and drafts.

Every passage here is invented. The gold trades are written the way a set
file writes them, so the tests also go through the set file's reader.

Names defined here: ``ZONE``, ``NOW``, ``sentence``, ``draft``, ``on_day``
and ``at_minute``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from evals.gold import Sentence, Split, sentences_from_json
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft
from ledger_hand.extraction.reply_table import Field

ZONE = "Europe/Budapest"
NOW = "2026-10-05T21:30:00+02:00"


def sentence(text: str, *trades: dict[str, object], name: str = "t1") -> Sentence:
    """A scored sentence of the debug set with these gold trades, as a set file writes them."""
    data = {
        "id": name,
        "text": text,
        "now": NOW,
        "zone": ZONE,
        "language": "zh",
        "group": "scored",
        "trades": list(trades),
    }
    return sentences_from_json([data], Split.DEBUG)[0]


def on_day(day: date) -> OccurredTime:
    return OccurredTime(day, TimePrecision.DAY, ZONE)


def at_minute(moment: datetime) -> OccurredTime:
    return OccurredTime(moment.replace(tzinfo=ZoneInfo(ZONE)), TimePrecision.MINUTE, ZONE)


def draft(raw_text: str = "", **fields: object) -> TradeDraft:
    """A draft from field names of the table; numbers may be given as text."""
    names = {
        "side": "side",
        "coin": "coin",
        "quantity": "quantity",
        "price": "price",
        "total": "total",
        "price_currency": "quote",
        "fee": "fee",
        "fee_currency": "fee_coin",
        "time": "occurred",
        "platform": "platform",
        "opinion": "note",
    }
    values: dict[str, object] = {"raw_text": raw_text or None}
    for name, value in fields.items():
        Field(name)
        if name in ("quantity", "price", "total", "fee") and isinstance(value, str):
            value = Decimal(value)
        if name == "side" and isinstance(value, str):
            value = Side(value)
        values[names[name]] = value
    return TradeDraft(**values)  # type: ignore[arg-type]
