"""Tests of the table of the ledger's eight tools and of how a tool list is compared with it."""

from __future__ import annotations

from typing import Any

from ledger_hand.ledger.link_tools import EXPECTED_TOOLS, TOP, differences, required_fields


def schema_of(name: str) -> dict[str, Any]:
    """A schema that requires exactly what the table expects of ``name``."""
    expected = EXPECTED_TOOLS[name]
    properties: dict[str, Any] = {}
    for where, fields in expected.items():
        if where.endswith("[]"):
            items = {"type": "object", "required": sorted(fields)}
            properties[where[:-2]] = {"type": "array", "items": items}
        elif where:
            properties[where] = {"type": "object", "required": sorted(fields)}
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if expected[TOP]:
        schema["required"] = sorted(expected[TOP])
    return schema


def listed() -> list[dict[str, Any]]:
    return [{"name": name, "inputSchema": schema_of(name)} for name in EXPECTED_TOOLS]


def test_the_table_names_the_ledgers_eight_tools_in_its_order() -> None:
    assert list(EXPECTED_TOOLS) == [
        "list_assets",
        "list_trades",
        "get_period_summary",
        "get_positions",
        "propose_trade_add",
        "propose_trade_update",
        "propose_trade_delete",
        "get_proposal_status",
    ]


def test_a_list_as_expected_has_no_differences() -> None:
    assert differences(listed()) == []


def test_a_renamed_or_missing_tool_is_a_difference() -> None:
    tools = listed()
    tools[0]["name"] = "list_coins"

    assert len(differences(tools)) == 1
    assert len(differences(listed()[1:])) == 1


def test_a_trade_field_no_longer_required_is_a_difference() -> None:
    tools = listed()
    trade = tools[4]["inputSchema"]["properties"]["trades"]["items"]
    trade["required"].remove("feeAssetId")

    (found,) = differences(tools)

    assert found.startswith("propose_trade_add.trades[]")
    assert "feeAssetId" in found


def test_a_new_required_field_at_the_top_is_a_difference() -> None:
    tools = listed()
    tools[0]["inputSchema"]["required"] = ["ledgerId"]

    assert differences(tools) == ["list_assets requires ['ledgerId'], expected []"]


def test_required_fields_reads_the_top_and_one_level_down() -> None:
    schema = {
        "required": ["a"],
        "properties": {
            "a": {"type": "object", "required": ["b"]},
            "c": {"type": "array", "items": {"type": "object", "required": ["d"]}},
            "e": {"type": "string"},
        },
    }

    assert required_fields(schema) == {
        TOP: frozenset({"a"}),
        "a": frozenset({"b"}),
        "c[]": frozenset({"d"}),
    }
