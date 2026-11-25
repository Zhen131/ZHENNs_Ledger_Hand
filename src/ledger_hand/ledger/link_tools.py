"""Link tools: the ledger's eight tools this program uses, and how to compare.

The ledger's assistant link lists its tools (``tools/list``), each with a
JSON schema of its arguments. ``EXPECTED_TOOLS`` writes down, once, what
this program was built against: the eight names it uses, and
for each the fields it requires, at the top and inside the one trade
(``trades[]`` for ``propose_trade_add``, ``trade`` for
``propose_trade_update``). The source is the ledger's
``assistant-link/README.md`` at ``dev@a6ba639``, "The eight tools".

``SENT_FIELDS`` writes down every field the real ledger's plug
(``link_ledger``) may send to each tool, required or not, at the top and
inside the one trade.

``required_fields`` and ``taken_fields`` read the required fields and all
the fields out of a tool's schema as the link lists it. ``differences``
says, one sentence each, where a list of tools does not fit this program.
Three rules, all of them, make a fit (decided on 2026-11-25, when the
ledger made most of a trade's fields optional):

1. each of the eight tools this program uses is listed;
2. every field the ledger requires of such a tool, this program sends;
3. every field this program sends, the tool takes.

A tool the ledger lists and this program does not use is no difference
(the ledger added a ninth, ``get_cash_balances``, on 2026-11-25); ``unused``
names such tools. A field the ledger required once and no longer requires
is no difference either; ``no_longer_required`` names such fields, so that
they are said. The ledger tier of the checks
(``scripts/ledger_link_check.py``) runs them against the real link, so a
change to the ledger's tools turns that tier red.

This module only compares data handed to it. It starts and reads nothing.

Names defined here: ``EXPECTED_TOOLS``, ``SENT_FIELDS``, ``TOP``,
``required_fields``, ``taken_fields``, ``differences``, ``unused`` and
``no_longer_required``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

# The key for a tool's own required fields, beside those inside a trade.
TOP = ""

_TRADE_FIELDS = frozenset(
    {"type", "assetId", "quantity", "price", "totalValue", "quoteAssetId", "fee", "feeAssetId"}
)

EXPECTED_TOOLS: Mapping[str, Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "list_assets": {TOP: frozenset()},
        "list_trades": {TOP: frozenset()},
        "get_period_summary": {TOP: frozenset({"startDate", "endDate"})},
        "get_positions": {TOP: frozenset()},
        "propose_trade_add": {
            TOP: frozenset({"trades"}),
            "trades[]": _TRADE_FIELDS | {"occurredDate"},
        },
        "propose_trade_update": {TOP: frozenset({"tradeId", "trade"}), "trade": _TRADE_FIELDS},
        "propose_trade_delete": {TOP: frozenset({"tradeId"})},
        "get_proposal_status": {TOP: frozenset({"proposalId"})},
    }
)


# Every field of a trade the plug may send, to record one or to change one.
_TRADE_SENT = _TRADE_FIELDS | {
    "costRate",
    "platform",
    "note",
    "occurredDate",
    "occurredTime",
    "occurredTimeZone",
}
_WHO = frozenset({"sourceText", "modelName"})

SENT_FIELDS: Mapping[str, Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "list_assets": {TOP: frozenset()},
        "list_trades": {TOP: frozenset({"startDate", "endDate", "assetId", "side", "pageToken"})},
        "get_period_summary": {TOP: frozenset({"startDate", "endDate"})},
        "get_positions": {TOP: frozenset()},
        "propose_trade_add": {TOP: _WHO | {"trades"}, "trades[]": _TRADE_SENT},
        "propose_trade_update": {TOP: _WHO | {"tradeId", "trade"}, "trade": _TRADE_SENT},
        "propose_trade_delete": {TOP: _WHO | {"tradeId"}},
        "get_proposal_status": {TOP: frozenset({"proposalId"})},
    }
)


def _nested(schema: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """The tool's own schema under ``TOP``, and each object or list of objects inside it."""
    found: dict[str, Mapping[str, Any]] = {TOP: schema}
    for name, value in (schema.get("properties") or {}).items():
        if not isinstance(value, dict):
            continue
        if value.get("type") == "object":
            found[name] = value
        items = value.get("items")
        if value.get("type") == "array" and isinstance(items, dict):
            found[f"{name}[]"] = items
    return found


def taken_fields(schema: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Every field a tool's input ``schema`` takes: its own, and those of a nested object."""
    return {
        where: frozenset(part.get("properties") or ()) for where, part in _nested(schema).items()
    }


def required_fields(schema: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """The required fields of a tool's input ``schema``: its own, and those of a nested trade.

    A property that is an object with required fields of its own is listed
    under its name; one that is a list of such objects, under its name with
    ``[]`` after it. Nothing deeper is looked at.
    """
    found = {TOP: frozenset(schema.get("required") or ())}
    for name, value in (schema.get("properties") or {}).items():
        if not isinstance(value, dict):
            continue
        if value.get("type") == "object" and value.get("required"):
            found[name] = frozenset(value["required"])
        items = value.get("items")
        if value.get("type") == "array" and isinstance(items, dict) and items.get("required"):
            found[f"{name}[]"] = frozenset(items["required"])
    return found


def differences(tools: Sequence[Mapping[str, Any]]) -> list[str]:
    """Where ``tools``, as the link lists them, differ from ``EXPECTED_TOOLS``; empty if nowhere."""
    names = [str(tool.get("name")) for tool in tools]
    missing = [name for name in EXPECTED_TOOLS if name not in names]
    if missing:
        return [f"the tools {missing} are not among the ledger's {names}"]
    found: list[str] = []
    for tool in tools:
        name = str(tool["name"])
        if name not in EXPECTED_TOOLS:
            continue
        schema = tool.get("inputSchema") or {}
        required, taken = required_fields(schema), taken_fields(schema)
        sent = SENT_FIELDS[name]
        for where in sorted(set(required) | set(sent)):
            place = f"{name}.{where}" if where else name
            not_sent = required.get(where, frozenset()) - sent.get(where, frozenset())
            if not_sent:
                found.append(f"{place} requires {sorted(not_sent)}, which this program never sends")
            not_taken = sent.get(where, frozenset()) - taken.get(where, frozenset())
            if not_taken:
                found.append(f"{place} does not take {sorted(not_taken)}, which this program sends")
    return found


def no_longer_required(tools: Sequence[Mapping[str, Any]]) -> list[str]:
    """Each field ``EXPECTED_TOOLS`` had required that the ledger no longer requires; said only."""
    found: list[str] = []
    for tool in tools:
        name = str(tool.get("name"))
        if name not in EXPECTED_TOOLS:
            continue
        required = required_fields(tool.get("inputSchema") or {})
        for where, fields in EXPECTED_TOOLS[name].items():
            dropped = fields - required.get(where, frozenset())
            if dropped:
                place = f"{name}.{where}" if where else name
                found.append(f"{place}: {', '.join(sorted(dropped))}")
    return found


def unused(tools: Sequence[Mapping[str, Any]]) -> list[str]:
    """The names of the tools the link lists that this program does not use, in its order."""
    return [str(tool.get("name")) for tool in tools if tool.get("name") not in EXPECTED_TOOLS]
