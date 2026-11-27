"""Tests of how the ledger's tool for exchange rates is checked in its list of tools.

The tool came with the ledger's dev 1b016ec; an older ledger lists nine
tools and still fits. The schema below is written from that ledger's
``assistant-link/README.md``. Invented data only.
"""

from __future__ import annotations

from typing import Any

from ledger_hand.ledger.link_tools import EXPECTED_TOOLS, RATE_FIELDS, differences, rate_tool

NULLABLE = {"type": ["string", "null"]}
RATES = {
    "name": "list_exchange_rates",
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {name: NULLABLE for name in sorted(RATE_FIELDS)},
    },
}


def test_a_ledger_without_the_tool_fits_and_says_so() -> None:
    assert rate_tool([{"name": "list_assets"}]) == (False, [])


def test_the_tool_with_its_five_fields_fits() -> None:
    assert rate_tool([RATES]) == (True, [])


def test_a_field_it_does_not_take_or_one_it_requires_is_a_difference() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "required": ["currencyCode"],
        "properties": {name: NULLABLE for name in ("currencyAssetId", "startDate")},
    }

    has, found = rate_tool([{"name": "list_exchange_rates", "inputSchema": schema}])

    assert has
    assert found == [
        "list_exchange_rates does not take ['endDate', 'otherCurrencyAssetId', 'pageToken']",
        "list_exchange_rates requires ['currencyCode'], which this program never sends",
    ]


def test_it_is_not_one_of_the_tools_every_ledger_must_list() -> None:
    assert "list_exchange_rates" not in EXPECTED_TOOLS
    assert "list_exchange_rates" not in str(differences([]))
