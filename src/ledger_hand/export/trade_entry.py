"""A saved trade's entry in the file: the ledger's fields of one trade.

Only the fields listed here are written; the ledger refuses a field it does
not know. Three it does know are never written: two sort keys and a fee rule,
which belong to the ledger's own records.

- Numbers are written by ``core.numbers.write_number``: exact, as text, never
  with an exponent.
- The time of the trade is written by ``core.timeparse.write_time``: a date,
  or a moment with its seconds and offset, beside the name of its time zone
  and its precision.
- The creation and change moments are written in UTC, to the second.
- The trade is always priced in USDT.
- Platform and note are left out altogether when there is none, or when they
  are empty: the ledger would refuse an empty platform, and an empty note says
  nothing.

Whether the trade is a sound one was decided before it became a record.
Nothing about it is checked again here.

Names defined here: ``trade_entry``.
"""

from __future__ import annotations

from ledger_hand.core.ledger_limits import QUOTE_CURRENCY
from ledger_hand.core.numbers import write_number
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.timeparse import write_time
from ledger_hand.export.moments import write_moment


def trade_entry(trade: StoredTrade) -> dict[str, object]:
    """The ledger's fields for ``trade``, in the ledger's order."""
    record = trade.record
    entry: dict[str, object] = {
        "id": trade.id,
        "occurredAt": write_time(record.occurred),
        "occurredTimeZone": record.occurred.time_zone,
        "timePrecision": record.occurred.precision.value,
        "type": record.side.value,
        "assetSymbol": record.coin,
        "quantity": write_number(record.quantity),
        "price": write_number(record.price),
        "totalValue": write_number(record.total),
        "currency": QUOTE_CURRENCY,
        "fee": write_number(record.fee),
        "feeCurrency": record.fee_coin,
    }
    if record.platform:
        entry["platform"] = record.platform
    if record.note:
        entry["note"] = record.note
    entry["rawText"] = record.raw_text
    entry["createdAt"] = write_moment(trade.created_at)
    entry["updatedAt"] = write_moment(trade.updated_at)
    return entry
