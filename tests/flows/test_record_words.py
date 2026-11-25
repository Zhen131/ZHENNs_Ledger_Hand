"""Tests of the program's words once the assistant has recorded what was said.

Every ending and every reason a trade was not sent has its sentence; every
stage of the recording flow either ends with one of them or goes on to the
proposal; each sentence can be filled in. Every value is invented.
"""

from __future__ import annotations

import string
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.flows.progress import Progress, Setting, Stage
from ledger_hand.flows.record_words import ENDING_WORDS, LEFT_OUT_WORDS, reply_for
from ledger_hand.flows.recorded import (
    SETTLED_STAGES,
    STAGE_ENDINGS,
    LeftOut,
    LeftOutTrade,
    Recorded,
    RecordEnding,
)

NOW = datetime(2026, 11, 24, 23, 55, tzinfo=ZoneInfo("Europe/Budapest"))
PROGRESS = Progress(Stage.NO_TRADE, "你好", Setting(NOW, "Europe/Budapest", BUILT_IN_ASSETS))


def test_every_ending_has_a_sentence() -> None:
    assert set(ENDING_WORDS) == set(RecordEnding)
    assert all(words.strip() for words in ENDING_WORDS.values())


def test_every_reason_a_trade_was_not_sent_has_a_sentence() -> None:
    assert set(LEFT_OUT_WORDS) == set(LeftOut)
    assert all("{number}" in words for words in LEFT_OUT_WORDS.values())


def test_every_stage_of_the_flow_ends_or_goes_on_to_the_proposal() -> None:
    assert set(STAGE_ENDINGS) | SETTLED_STAGES == set(Stage)
    assert not set(STAGE_ENDINGS) & SETTLED_STAGES


@pytest.mark.parametrize("ending", list(RecordEnding))
def test_each_ending_can_be_said(ending: RecordEnding) -> None:
    said = reply_for(Recorded(ending=ending, progress=PROGRESS, missing_money="USDT"))

    if ending is not RecordEnding.ASKING:
        assert said.strip()
    assert "{" not in said


@pytest.mark.parametrize("why", list(LeftOut))
def test_each_reason_names_the_trade(why: LeftOut) -> None:
    left = LeftOutTrade(number=2, why=why, code="SOL", reason="the fee is missing")
    said = reply_for(
        Recorded(ending=RecordEnding.NOTHING_TO_SEND, progress=PROGRESS, left_out=(left,))
    )

    assert "Trade 2" in said.splitlines()[1]


def test_the_words_are_plain_english_and_carry_no_figure() -> None:
    allowed = set(string.ascii_letters + string.punctuation + " ")
    for words in (*ENDING_WORDS.values(), *LEFT_OUT_WORDS.values()):
        assert set(words) <= allowed, words
        assert not any(character.isdigit() for character in words), words
