"""The tools the assistant's model is handed: eight, by name, with what each takes.

The model may fill a tool's arguments in two ways only, and every argument
says which (``ArgumentKind``): it picks one of a fixed list of choices, or
it copies a piece of what the user said, word for word. It never writes a
number or a date of its own: what was copied is turned into a number or a
moment by the program, later, and checked against the user's words first
(``judging``). So no argument here is a number, and none is a date in a
format; a test walks the list to keep it so.

The eight tools, their names as the ledger's list of tools has them:

- ``list_assets``, ``get_positions``: read the ledger; they take nothing.
- ``get_proposal_status``: where the last proposal of this chat stands.
- ``list_trades``: trades by ``period`` (copied, such as "10月6号"),
  ``asset`` (copied, such as "BTC") and ``side`` (a choice: buy or sell).
- ``get_period_summary``: the sums of a ``period`` (copied), of an
  ``asset`` (copied).
- ``propose_trade_add``: the user is telling of a trade already filled.
  It takes nothing: the trade itself is read from the user's words by the
  program, not handed over by the model.
- ``propose_trade_update``: change one trade, found by the same three
  arguments as ``list_trades``, or by ``trade`` (copied: which of the
  trades just listed the user picks, such as "第二笔"); ``field`` (a choice,
  required: which part to change) and ``new_value`` (copied, required).
- ``propose_trade_delete``: delete one trade, found the same way.

Every argument may be left out unless it is marked required. A tool's
schema allows no argument it does not name.

Names defined here: ``ToolName``, ``ArgumentKind``, ``Need``, ``Argument``,
``Tool``, ``SIDE_CHOICES``, ``FIELD_CHOICES``, ``NUMBER_FIELDS``, ``TOOLS``,
``tool_named`` and ``tool_specs``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ledger_hand.ports import JsonSchema, ToolSpec


class ToolName(enum.Enum):
    """The eight tools; the values are the names the model is told."""

    LIST_ASSETS = "list_assets"
    LIST_TRADES = "list_trades"
    GET_PERIOD_SUMMARY = "get_period_summary"
    GET_POSITIONS = "get_positions"
    PROPOSE_TRADE_ADD = "propose_trade_add"
    PROPOSE_TRADE_UPDATE = "propose_trade_update"
    PROPOSE_TRADE_DELETE = "propose_trade_delete"
    GET_PROPOSAL_STATUS = "get_proposal_status"


class ArgumentKind(enum.Enum):
    """The only two ways the model may fill an argument."""

    CHOICE = "choice"
    """One of a fixed list of words."""
    COPIED = "copied"
    """A piece of what the user said, copied word for word."""


class Need(enum.Enum):
    """Whether an argument must be given."""

    REQUIRED = "required"
    OPTIONAL = "optional"


@dataclass(frozen=True, kw_only=True)
class Argument:
    """One argument of a tool: its name, how it is filled, what it means, and its choices."""

    name: str
    kind: ArgumentKind
    description: str
    need: Need = Need.OPTIONAL
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.kind is ArgumentKind.CHOICE) != bool(self.choices):
            raise ValueError("a choice has its choices, and a copied argument has none")


@dataclass(frozen=True, kw_only=True)
class Tool:
    """One tool: its name, what it does, and its arguments."""

    name: ToolName
    description: str
    arguments: tuple[Argument, ...] = ()

    def argument(self, name: str) -> Argument | None:
        """The argument called ``name``; ``None`` when the tool has none of that name."""
        return next((argument for argument in self.arguments if argument.name == name), None)


SIDE_CHOICES = ("buy", "sell")
# The parts of a trade that can be changed.
FIELD_CHOICES = (
    "quantity",
    "price",
    "total",
    "quote_currency",
    "fee",
    "fee_currency",
    "time",
    "platform",
    "note",
    "side",
    "asset",
)
# The parts whose new value is a number, checked as one when it is copied.
NUMBER_FIELDS = frozenset({"quantity", "price", "total", "fee"})

_COPY = "Copy it word for word from the user's message; never convert or rewrite it."
_PERIOD = Argument(
    name="period",
    kind=ArgumentKind.COPIED,
    description=(
        "The time the user named, such as '10月6号' or 'last month', in the user's own "
        f"language: 'last week' stays 'last week', never '上周'. {_COPY}"
    ),
)
_ASSET = Argument(
    name="asset",
    kind=ArgumentKind.COPIED,
    description=f"The asset the user named, such as 'BTC'. {_COPY}",
)
_SIDE = Argument(
    name="side",
    kind=ArgumentKind.CHOICE,
    description="Buys or sells only, when the user said which.",
    choices=SIDE_CHOICES,
)
_TRADE = Argument(
    name="trade",
    kind=ArgumentKind.COPIED,
    description=(
        "Only when the user picks one of the trades just listed: the words they picked it "
        f"with, such as '第二笔'. {_COPY}"
    ),
)
_FIND_ONE = (_PERIOD, _ASSET, _SIDE, _TRADE)

TOOLS = (
    Tool(
        name=ToolName.LIST_ASSETS,
        description="List the assets in the ledger: name, code, kind, whether it prices trades.",
    ),
    Tool(
        name=ToolName.LIST_TRADES,
        description=(
            "List trades already in the ledger, narrowed by time, asset and side. Use it to look "
            "trades up, and to find the trade before changing or deleting it."
        ),
        arguments=(_PERIOD, _ASSET, _SIDE),
    ),
    Tool(
        name=ToolName.GET_PERIOD_SUMMARY,
        description=(
            "Sums for a stretch of time: money spent on buys, money received from sells, fees, "
            "number of trades, realized profit or loss; one set for each currency."
        ),
        arguments=(_PERIOD, _ASSET),
    ),
    Tool(
        name=ToolName.GET_POSITIONS,
        description="What the user holds now: quantity, cost and unrealized profit or loss.",
    ),
    Tool(
        name=ToolName.PROPOSE_TRADE_ADD,
        description=(
            "The user's message tells of one or more trades that have ALREADY been filled, to "
            "record. The program reads the trades from the user's own words; give nothing. "
            "Nothing is written until the user confirms in the ledger."
        ),
    ),
    Tool(
        name=ToolName.PROPOSE_TRADE_UPDATE,
        description=(
            "Change one existing trade. Say which trade the same way as for list_trades, which "
            "part to change, and the new value. Nothing is written until the user confirms."
        ),
        arguments=(
            *_FIND_ONE,
            Argument(
                name="field",
                kind=ArgumentKind.CHOICE,
                description="Which part of the trade to change.",
                need=Need.REQUIRED,
                choices=FIELD_CHOICES,
            ),
            Argument(
                name="new_value",
                kind=ArgumentKind.COPIED,
                description=f"The value the user wants it changed to. {_COPY}",
                need=Need.REQUIRED,
            ),
        ),
    ),
    Tool(
        name=ToolName.PROPOSE_TRADE_DELETE,
        description=(
            "Delete one existing trade. Say which trade the same way as for list_trades. "
            "Nothing is deleted until the user confirms."
        ),
        arguments=_FIND_ONE,
    ),
    Tool(
        name=ToolName.GET_PROPOSAL_STATUS,
        description=(
            "Where the last proposal of this chat stands: pending, saved, rejected or void."
        ),
    ),
)

_BY_NAME = {tool.name.value: tool for tool in TOOLS}


def tool_named(name: str) -> Tool | None:
    """The tool the model calls ``name``; ``None`` when there is no such tool."""
    return _BY_NAME.get(name)


def _schema(tool: Tool) -> JsonSchema:
    properties: dict[str, object] = {}
    for argument in tool.arguments:
        described: dict[str, object] = {"type": "string", "description": argument.description}
        if argument.kind is ArgumentKind.CHOICE:
            described["enum"] = list(argument.choices)
        properties[argument.name] = described
    return {
        "type": "object",
        "properties": properties,
        "required": [arg.name for arg in tool.arguments if arg.need is Need.REQUIRED],
        "additionalProperties": False,
    }


def tool_specs() -> tuple[ToolSpec, ...]:
    """The tools as the model port hands them to the model."""
    return tuple(
        ToolSpec(name=tool.name.value, description=tool.description, parameters=_schema(tool))
        for tool in TOOLS
    )
