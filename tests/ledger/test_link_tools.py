"""Tests of the table of the ledger's eight tools and of how a tool list is compared with it."""

from __future__ import annotations

from typing import Any

from ledger_hand.ledger.link_tools import (
    EXPECTED_TOOLS,
    SENT_FIELDS,
    TOP,
    differences,
    no_longer_required,
    required_fields,
    taken_fields,
    unused,
)


def schema_of(name: str) -> dict[str, Any]:
    """A schema that takes what this program sends to ``name`` and requires what the table
    expects of it."""
    expected, sent = EXPECTED_TOOLS[name], SENT_FIELDS[name]
    properties: dict[str, Any] = {field: {"type": "string"} for field in sent[TOP]}
    for where, fields in sent.items():
        part = {
            "type": "object",
            "properties": {field: {"type": "string"} for field in fields},
            "required": sorted(expected.get(where, frozenset())),
        }
        if where.endswith("[]"):
            properties[where[:-2]] = {"type": "array", "items": part}
        elif where:
            properties[where] = part
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


def test_a_trade_field_no_longer_required_is_no_difference_and_is_said() -> None:
    tools = listed()
    trade = tools[4]["inputSchema"]["properties"]["trades"]["items"]
    trade["required"] = ["assetId", "type"]

    assert differences(tools) == []
    (said,) = no_longer_required(tools)
    assert said.startswith("propose_trade_add.trades[]: ")
    assert "feeAssetId" in said and "assetId," not in said


def test_a_new_required_field_this_program_never_sends_is_a_difference() -> None:
    tools = listed()
    tools[0]["inputSchema"]["required"] = ["ledgerId"]

    assert differences(tools) == [
        "list_assets requires ['ledgerId'], which this program never sends"
    ]


def test_a_field_this_program_sends_that_the_tool_no_longer_takes_is_a_difference() -> None:
    tools = listed()
    del tools[4]["inputSchema"]["properties"]["sourceText"]
    del tools[4]["inputSchema"]["properties"]["trades"]["items"]["properties"]["note"]

    assert differences(tools) == [
        "propose_trade_add does not take ['sourceText'], which this program sends",
        "propose_trade_add.trades[] does not take ['note'], which this program sends",
    ]


def test_a_tool_this_program_does_not_use_is_no_difference_and_is_named() -> None:
    tools = [*listed(), {"name": "get_cash_balances", "inputSchema": {"type": "object"}}]

    assert differences(tools) == []
    assert unused(tools) == ["get_cash_balances"]


def test_every_field_the_table_expects_is_one_this_program_sends() -> None:
    for name, expected in EXPECTED_TOOLS.items():
        for where, fields in expected.items():
            assert fields <= SENT_FIELDS[name][where], (name, where)


def test_taken_fields_reads_the_top_and_one_level_down() -> None:
    schema = {
        "properties": {
            "a": {"type": "object", "properties": {"b": {}}},
            "c": {"type": "array", "items": {"type": "object", "properties": {"d": {}}}},
        },
    }

    assert taken_fields(schema) == {
        TOP: frozenset({"a", "c"}),
        "a": frozenset({"b"}),
        "c[]": frozenset({"d"}),
    }


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
