"""Tests of the small schema check the live check relies on. They need no model."""

from __future__ import annotations

import pytest

from tests.live.schema_check import problems_with
from tests.live.small_table import SMALL_TABLE


@pytest.mark.parametrize(
    "value",
    [{"fruit": "apple", "count": 3}, {"fruit": "", "count": 0}, {"fruit": "pear", "count": -2}],
)
def test_values_that_follow_the_small_table_pass(value: object) -> None:
    assert problems_with(value, SMALL_TABLE) == []


@pytest.mark.parametrize(
    ("value", "complaint"),
    [
        ({"fruit": "apple"}, "'count' is missing"),
        ({"count": 3}, "'fruit' is missing"),
        ({"fruit": "apple", "count": 3, "colour": "red"}, "not in the table"),
        ({"fruit": "apple", "count": "3"}, "expected integer"),
        ({"fruit": "apple", "count": 3.0}, "expected integer"),
        ({"fruit": "apple", "count": True}, "expected integer"),
        ({"fruit": 7, "count": 3}, "expected string"),
        ({"fruit": None, "count": 3}, "expected string"),
        (["apple", 3], "expected object"),
        ("apple", "expected object"),
        (None, "expected object"),
    ],
)
def test_values_that_break_the_small_table_are_reported(value: object, complaint: str) -> None:
    found = problems_with(value, SMALL_TABLE)

    assert found
    assert any(complaint in problem for problem in found)


def test_enumerations_are_checked() -> None:
    schema = {"type": "string", "enum": ["buy", "sell"]}

    assert problems_with("buy", schema) == []
    assert problems_with("hold", schema) != []


def test_a_keyword_the_check_does_not_know_is_refused() -> None:
    with pytest.raises(ValueError, match="does not know"):
        problems_with({"a": 1}, {"type": "object", "minProperties": 1})


def test_a_type_the_check_does_not_know_is_refused() -> None:
    with pytest.raises(ValueError, match="does not know the type"):
        problems_with(1, {"type": "decimal"})
