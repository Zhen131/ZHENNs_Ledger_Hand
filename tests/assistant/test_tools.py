"""Tests of the tools the model is handed: it can fill no number and no date.

Every argument of every tool is either one of a fixed list of choices, or
text copied from the user's words; none is a number, and none asks for a
date in a format. The names are the ledger's eight, and each schema allows
no argument it does not name.
"""

from __future__ import annotations

import re

from ledger_hand.assistant.tools import TOOLS, ArgumentKind, ToolName, tool_specs

# Words that would ask the model to write a date or a time in a format of its own.
DATE_FORMATS = re.compile(r"YYYY|MM-DD|HH:MM|ISO|date-time|format", re.IGNORECASE)


def test_the_eight_tools_have_the_ledgers_names() -> None:
    assert [spec.name for spec in tool_specs()] == [name.value for name in ToolName]
    assert {name.value for name in ToolName} == {
        "list_assets",
        "list_trades",
        "get_period_summary",
        "get_positions",
        "propose_trade_add",
        "propose_trade_update",
        "propose_trade_delete",
        "get_proposal_status",
    }


def test_every_argument_is_a_choice_or_copied_text_never_a_number_or_a_date() -> None:
    for tool, spec in zip(TOOLS, tool_specs(), strict=True):
        properties = spec.parameters["properties"]
        assert isinstance(properties, dict)
        assert set(properties) == {argument.name for argument in tool.arguments}
        for argument in tool.arguments:
            schema = properties[argument.name]
            assert schema["type"] == "string", (tool.name, argument.name)
            assert "format" not in schema and "pattern" not in schema
            assert not DATE_FORMATS.search(schema["description"]), (tool.name, argument.name)
            if argument.kind is ArgumentKind.CHOICE:
                assert schema["enum"] == list(argument.choices)
            else:
                assert argument.kind is ArgumentKind.COPIED
                assert "enum" not in schema
                assert "word for word" in schema["description"]


def test_no_schema_allows_an_argument_it_does_not_name() -> None:
    for spec in tool_specs():
        assert spec.parameters["additionalProperties"] is False


def test_recording_takes_nothing_and_changing_needs_a_field_and_a_new_value() -> None:
    specs = {spec.name: spec.parameters for spec in tool_specs()}

    assert specs["propose_trade_add"]["properties"] == {}
    assert specs["propose_trade_update"]["required"] == ["field", "new_value"]
    for name in ("propose_trade_update", "propose_trade_delete"):
        assert {"period", "asset", "side", "trade"} <= set(specs[name]["properties"])  # type: ignore[arg-type]
    field = specs["propose_trade_update"]["properties"]["field"]  # type: ignore[index]
    assert {"quote_currency", "fee_currency"} <= set(field["enum"])
