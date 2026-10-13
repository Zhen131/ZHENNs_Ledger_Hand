"""Tests of the clock-free gate's judging, fed the layering tests' tables.

The gate in ``test_repo_clock_free_parts.py`` checks ``asking/`` and
``flows/`` of the real package straight from their source. Here its one
judging function, the same one the gate calls, is fed every way of reading
the clock or the machine's zone that the layering tests list, and must find
each one; code that handles time passed in, which the gate has always let
through, must still pass.
"""

from __future__ import annotations

import pytest

from tests.guardrails.test_layering import (
    CLOCK_READS,
    LOCAL_ZONE_READS,
    MORE_LOCAL_ZONE_READS,
    MORE_PURE_ZONE_CODE,
    PURE_TIME_CODE,
    TIME_MODULE_CLOCK_READS,
    TIME_MODULE_ZONE_READS,
    lines,
)
from tests.guardrails.test_repo_clock_free_parts import Rule, clock_problems

# Written out again by hand: the three the gate used to let through, so that
# they stay covered even if the tables above change.
ONCE_MISSED = [
    lines("from datetime import datetime", "read_clock = datetime.now"),
    lines("def local(moment):", "    return moment.astimezone(None)"),
    lines("def local(moment):", "    return moment.astimezone(tz=None)"),
]

# The other clock methods handed over without being called, as the layering
# check treats them.
HANDED_OVER = [
    lines("from datetime import datetime", "read_clock = datetime.utcnow"),
    lines("from datetime import date", "read_day = date.today"),
    lines("import datetime", "read_clock = datetime.datetime.now"),
]

# The gate refuses ``fromtimestamp`` whatever zone it is given, as it always has.
WITH_FROMTIMESTAMP = [source for source in PURE_TIME_CODE if "fromtimestamp" in source]
ALWAYS_LET_THROUGH = [
    *(source for source in PURE_TIME_CODE if "fromtimestamp" not in source),
    *MORE_PURE_ZONE_CODE,
    # How the flows read the moment they are handed.
    lines("def moment(setting):", "    return setting.now"),
    lines("def day(setting, zone):", "    return setting.now.astimezone(zone).date()"),
]


def rules_found(source: str) -> set[Rule]:
    return {problem.rule for problem in clock_problems(source)}


@pytest.mark.parametrize("source", CLOCK_READS + LOCAL_ZONE_READS + MORE_LOCAL_ZONE_READS)
def test_the_gate_finds_every_read_of_the_clock_or_the_zone(source: str) -> None:
    assert Rule.CLOCK_OR_ZONE in rules_found(source)


@pytest.mark.parametrize("source", TIME_MODULE_CLOCK_READS + TIME_MODULE_ZONE_READS)
def test_the_gate_finds_every_read_through_the_time_module(source: str) -> None:
    assert Rule.TIME_MODULE in rules_found(source)


@pytest.mark.parametrize("source", ONCE_MISSED + HANDED_OVER)
def test_the_gate_finds_what_it_used_to_let_through(source: str) -> None:
    assert rules_found(source) == {Rule.CLOCK_OR_ZONE}


def test_the_ones_once_missed_are_in_the_tables() -> None:
    assert all(source in CLOCK_READS + LOCAL_ZONE_READS for source in ONCE_MISSED)


@pytest.mark.parametrize("source", ALWAYS_LET_THROUGH)
def test_the_gate_still_lets_time_passed_in_through(source: str) -> None:
    assert clock_problems(source) == []


@pytest.mark.parametrize("source", WITH_FROMTIMESTAMP)
def test_the_gate_still_refuses_fromtimestamp_even_with_a_zone(source: str) -> None:
    assert rules_found(source) == {Rule.CLOCK_OR_ZONE}


def test_the_tables_hold_two_fromtimestamp_calls_with_a_zone() -> None:
    # Written out by hand, so that the split above cannot quietly empty either side.
    assert len(WITH_FROMTIMESTAMP) == 2
    assert len(ALWAYS_LET_THROUGH) == len(PURE_TIME_CODE) - 2 + len(MORE_PURE_ZONE_CODE) + 2


def test_a_problem_names_its_line() -> None:
    source = lines('"""Flows."""', "", "def local(moment):", "    return moment.astimezone(None)")

    (problem,) = clock_problems(source)

    assert problem.line == 4
    assert problem.rule is Rule.CLOCK_OR_ZONE
