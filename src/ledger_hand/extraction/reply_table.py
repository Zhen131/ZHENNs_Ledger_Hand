"""The table the model fills: one row per trade, each cell a phrase copied from the passage.

The table is flat on purpose: a list of rows, and in each row one cell per
field, every cell a piece of text. Small models lose their way in tables
nested deeper than that, and plain field names help them more than clever
ones.

Every cell but ``side`` holds a phrase copied from the passage, or is empty
when the passage does not say it. ``side`` is chosen, not copied: it is
``buy``, ``sell`` or empty.

``REPLY_TABLE`` is the table written as a JSON schema, which is handed to the
model with every call so that the model server holds the reply to it.
``reply_parser`` reads a reply against the same fields.

Names defined here: ``Field``, ``COPIED_FIELDS``, ``SIDE_WORDS``,
``TRADES_KEY`` and ``REPLY_TABLE``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping

from ledger_hand.core.trade import Side


class Field(enum.Enum):
    """One cell of a row; the value is the field's name in the table."""

    SIDE = "side"
    COIN = "coin"
    QUANTITY = "quantity"
    PRICE = "price"
    TOTAL = "total"
    PRICE_CURRENCY = "price_currency"
    FEE = "fee"
    FEE_CURRENCY = "fee_currency"
    TIME = "time"
    PLATFORM = "platform"
    OPINION = "opinion"


# The fields whose cell is a phrase copied from the passage, in table order.
COPIED_FIELDS: tuple[Field, ...] = tuple(field for field in Field if field is not Field.SIDE)

# What the side cell may hold, and what each word means. The empty word means
# the passage does not say.
SIDE_WORDS: Mapping[str, Side | None] = {"buy": Side.BUY, "sell": Side.SELL, "": None}

# The one key of the reply object; its value is the list of rows.
TRADES_KEY = "trades"


def _row_schema() -> dict[str, object]:
    properties: dict[str, object] = {
        field.value: {"type": "string"} for field in Field if field is not Field.SIDE
    }
    properties[Field.SIDE.value] = {"type": "string", "enum": list(SIDE_WORDS)}
    ordered = {field.value: properties[field.value] for field in Field}
    return {
        "type": "object",
        "properties": ordered,
        "required": [field.value for field in Field],
        "additionalProperties": False,
    }


REPLY_TABLE: Mapping[str, object] = {
    "type": "object",
    "properties": {TRADES_KEY: {"type": "array", "items": _row_schema()}},
    "required": [TRADES_KEY],
    "additionalProperties": False,
}
