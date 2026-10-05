"""The invented question and the small table the live check hands the real model.

Names defined here: ``QUESTION``, ``SMALL_TABLE``.
"""

from __future__ import annotations

from ledger_hand.ports import Message, Role

QUESTION = (
    Message(Role.SYSTEM, "You answer questions about an invented fruit stall, in JSON."),
    Message(
        Role.USER,
        "Today the invented stall sold 3 apples and 2 pears. "
        "Which fruit sold more, and how many of it were sold?",
    ),
)

SMALL_TABLE: dict[str, object] = {
    "type": "object",
    "properties": {
        "fruit": {"type": "string"},
        "count": {"type": "integer"},
    },
    "required": ["fruit", "count"],
    "additionalProperties": False,
}
