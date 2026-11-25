"""Link tools: the ledger's eight tools as this program expects them, and how to compare.

The ledger's assistant link lists eight tools (``tools/list``), each with a
JSON schema of its arguments. ``EXPECTED_TOOLS`` writes down, once, what
this program was built against: the eight names in the ledger's order, and
for each the fields it requires, at the top and inside the one trade
(``trades[]`` for ``propose_trade_add``, ``trade`` for
``propose_trade_update``). The source is the ledger's
``assistant-link/README.md`` at ``dev@a6ba639``, "The eight tools".

``required_fields`` reads the same thing out of a tool's schema as the link
lists it, and ``differences`` says, one sentence each, where a list of
tools differs from what is expected. The ledger tier of the checks
(``scripts/ledger_link_check.py``) runs them against the real link, so a
change to the ledger's tools turns that tier red.

This module only compares data handed to it. It starts and reads nothing.

Names defined here: ``EXPECTED_TOOLS``, ``TOP``, ``required_fields`` and
``differences``.
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
    if names != list(EXPECTED_TOOLS):
        return [f"the tools are {names}, not {list(EXPECTED_TOOLS)}"]
    found: list[str] = []
    for tool in tools:
        name = str(tool["name"])
        listed = required_fields(tool.get("inputSchema") or {})
        expected = dict(EXPECTED_TOOLS[name])
        for where in sorted(set(listed) | set(expected)):
            have, want = listed.get(where, frozenset()), expected.get(where, frozenset())
            if have != want:
                place = f"{name}.{where}" if where else name
                found.append(f"{place} requires {sorted(have)}, expected {sorted(want)}")
    return found
