"""How a saved trade, and a bookkeeping moment, become the values of a row of the book, and back.

A trade is kept field by field. Numbers are written the way the ledger
writes them (``core.numbers.write_number``) and the time the way the ledger
writes it (``core.timeparse.write_time``), beside its precision and the name
of its time zone: all as text, never as a floating-point number, so a trade
read back is equal to the one saved, down to which amount the program worked
out. Bookkeeping moments (created, changed, saved, exported, confirmed) are
kept in UTC to the microsecond, so they come back as the same instants.

Reading a row back checks every value as it goes. A value that cannot be what
the book wrote raises ``ValueError`` or ``TypeError``; the store reports that
as a damaged book.

Names defined here: ``TRADE_COLUMNS``, ``trade_values``, ``trade_from``,
``moment_text`` and ``moment_from``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from ledger_hand.core.numbers import write_number
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.timeparse import write_time
from ledger_hand.core.trade import Amount, OccurredTime, Side, TimePrecision, TradeRecord

# The columns of a trade's row that hold the trade itself, in the order of the table.
TRADE_COLUMNS = (
    "id",
    "side",
    "coin",
    "quantity",
    "price",
    "total",
    "derived",
    "fee",
    "fee_coin",
    "occurred",
    "time_precision",
    "time_zone",
    "raw_text",
    "platform",
    "note",
    "created_at",
    "updated_at",
)


def moment_text(moment: datetime) -> str:
    """``moment`` in UTC, to the microsecond, as in ``2026-10-08T18:30:15.123456+00:00``."""
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def moment_from(text: object) -> datetime:
    """The moment ``text`` holds, in UTC; refused unless it is one this module wrote."""
    moment = datetime.fromisoformat(_text(text))
    if moment.utcoffset() is None:
        raise ValueError(f"a kept moment has no offset: {text!r}")
    return moment.astimezone(timezone.utc)


def trade_values(trade: StoredTrade) -> dict[str, str | None]:
    """The values of the row that keeps ``trade``, by column."""
    record = trade.record
    return {
        "id": trade.id,
        "side": record.side.value,
        "coin": record.coin,
        "quantity": write_number(record.quantity),
        "price": write_number(record.price),
        "total": write_number(record.total),
        "derived": None if record.derived is None else record.derived.value,
        "fee": write_number(record.fee),
        "fee_coin": record.fee_coin,
        "occurred": write_time(record.occurred),
        "time_precision": record.occurred.precision.value,
        "time_zone": record.occurred.time_zone,
        "raw_text": record.raw_text,
        "platform": record.platform,
        "note": record.note,
        "created_at": moment_text(trade.created_at),
        "updated_at": moment_text(trade.updated_at),
    }


def trade_from(values: Mapping[str, object]) -> StoredTrade:
    """The trade a row keeps; ``ValueError`` or ``TypeError`` when a value cannot be one."""
    derived = values["derived"]
    record = TradeRecord(
        side=Side(_text(values["side"])),
        coin=_text(values["coin"]),
        quantity=_number(values["quantity"]),
        price=_number(values["price"]),
        total=_number(values["total"]),
        derived=None if derived is None else Amount(_text(derived)),
        fee=_number(values["fee"]),
        fee_coin=_text(values["fee_coin"]),
        occurred=_occurred(values["occurred"], values["time_precision"], values["time_zone"]),
        raw_text=_text(values["raw_text"]),
        platform=_optional_text(values["platform"]),
        note=_optional_text(values["note"]),
    )
    return StoredTrade(
        id=_text(values["id"]),
        record=record,
        created_at=moment_from(values["created_at"]),
        updated_at=moment_from(values["updated_at"]),
    )


def _occurred(text: object, precision: object, zone: object) -> OccurredTime:
    kept_precision = TimePrecision(_text(precision))
    written = _text(text)
    value: date | datetime
    if kept_precision is TimePrecision.DAY:
        value = date.fromisoformat(written)
    else:
        value = datetime.fromisoformat(written)
    return OccurredTime(value, kept_precision, _text(zone))


def _number(text: object) -> Decimal:
    try:
        number = Decimal(_text(text))
    except InvalidOperation as error:
        raise ValueError(f"a kept number is not a number: {text!r}") from error
    if not number.is_finite():
        raise ValueError(f"a kept number is not finite: {text!r}")
    return number


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"a kept value is not text: {value!r}")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)
