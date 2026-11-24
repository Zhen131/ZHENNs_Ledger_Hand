"""Tests of the assistant's system prompt: the moment and zone are filled in, and the rules hold.

The moment is written in the zone, with its weekday, to the minute. The
words say the rules the program holds the model to: tools only, no orders,
no forecasts, no advice, an order still waiting is no trade, questions go
to a read tool, a trade is found before it is changed, arguments are
copied, the reply is in the user's language.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ledger_hand.assistant.prompting import AssistantPrompt, system_message
from ledger_hand.assistant.prompts.assistant_first import ASSISTANT_FIRST
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import Role


def test_the_moment_is_written_in_the_zone_with_its_weekday() -> None:
    message = system_message(ASSISTANT_FIRST, INVENTED_NOW.astimezone(timezone.utc), INVENTED_ZONE)

    assert message.role is Role.SYSTEM
    assert "2026-11-24 (Tuesday) 23:55, time zone Europe/Budapest" in message.content


@pytest.mark.parametrize(
    "rule",
    [
        "only through the tools",
        "never place, buy or sell",
        "never say whether a price will rise or fall",
        "never advise",
        "still waiting to be filled is not a trade",
        "Never answer from memory",
        "first call list_trades",
        "copying the user's own words exactly",
        "Never convert a time into a date",
        "Reply in the user's language",
    ],
)
def test_the_first_version_says_each_rule(rule: str) -> None:
    assert rule in ASSISTANT_FIRST.words


def test_a_moment_without_an_offset_is_refused() -> None:
    with pytest.raises(ValueError):
        system_message(ASSISTANT_FIRST, datetime(2026, 11, 24, 23, 55), INVENTED_ZONE)


def test_a_version_holds_each_mark_once() -> None:
    with pytest.raises(ValueError):
        AssistantPrompt(name="broken", words="no marks")
