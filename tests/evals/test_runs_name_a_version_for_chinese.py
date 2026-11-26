"""Tests of the measures that may name an extraction version for Chinese.

``judged_run`` hands a passage to the version named only when it holds a
Chinese character, through the same function the assistant asks; ``first``
and the other older versions are still handed every passage.
``spoken_run`` and ``stock_run`` hand the version named to ``say``, and say
in the results which version read Chinese and which read English. No real
model is called; every sentence is invented or taken from the share set.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import evals.judged_run as judged_run
import evals.spoken_run as spoken_run
import evals.stock_run as stock_run
from evals.gold import DEBUG_SET, Split, load_set
from evals.run import Backend
from evals.stock_set import load_stock_set
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.extraction.prompts.spoken1 import SPOKEN_PROMPT_1
from ledger_hand.flows.progress import DEFAULT_TUNING

BACKEND = Backend(
    model=None,  # type: ignore[arg-type]
    name="stand-in",
    fingerprint="-",
    server_version="-",
    base_url="-",
    parameters={},
)


def _handed_to_start(monkeypatch: pytest.MonkeyPatch, text: str, extract: Any) -> str:
    seen: list[str] = []

    def start(passage: str, model: object, **named: Any) -> object:
        seen.append(named["extract_prompt"].name)
        return object()

    monkeypatch.setattr(judged_run, "start", start)
    sentence = replace(load_set(DEBUG_SET, Split.DEBUG)[0], text=text)
    judged_run._one(sentence, None, SCREEN_PROMPT_2, extract)  # type: ignore[arg-type]
    return seen[0]


def test_judged_run_reads_chinese_with_a_version_for_chinese_and_english_with_first_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _handed_to_start(monkeypatch, "昨天买了 2 ETH", SPOKEN_PROMPT_1) == "spoken-1"
    assert _handed_to_start(monkeypatch, "Bought 2 ETH yesterday", SPOKEN_PROMPT_1) == "first-3"


def test_judged_run_hands_an_older_version_every_passage(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _handed_to_start(monkeypatch, "Bought 2 ETH yesterday", FIRST_PROMPT) == "first"
    assert _handed_to_start(monkeypatch, "昨天买了 2 ETH", FIRST_PROMPT_3) == "first-3"


def test_judged_run_knows_the_versions_for_chinese_and_names_both_in_its_first_line() -> None:
    assert set(judged_run.CHINESE_EXTRACTS) == {"first-3", "spoken-1", "spoken-2"}
    assert judged_run.EXTRACTS["spoken-1"] is SPOKEN_PROMPT_1
    options = argparse.Namespace(
        screen="screen-2", extract="spoken-1", hold_other_unit=True, tidy=False
    )

    head = judged_run._head(options, DEBUG_SET, BACKEND, judged_run.datetime.now())

    assert (head["extraction_prompt"], head["english_extraction_prompt"]) == (
        "spoken-1",
        "first-3",
    )


def test_judged_run_says_nothing_more_for_an_older_version() -> None:
    options = argparse.Namespace(
        screen="screen-2", extract="first-3", hold_other_unit=True, tidy=False
    )

    head = judged_run._head(options, DEBUG_SET, BACKEND, judged_run.datetime.now())

    assert "english_extraction_prompt" not in head


def test_stock_run_hands_the_version_named_to_the_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []
    monkeypatch.setattr(stock_run, "say", lambda *_, **named: seen.append(named))
    sentence = load_stock_set().sentences[0]

    stock_run._said(
        sentence,
        None,
        6,
        DEFAULT_TUNING,
        stock_run.STOCK_SET,
        SPOKEN_PROMPT_1,  # type: ignore[arg-type]
    )
    stock_run._said(sentence, None, 6, DEFAULT_TUNING, stock_run.STOCK_SET)  # type: ignore[arg-type]

    assert [named["extract_for_chinese"] for named in seen] == [SPOKEN_PROMPT_1, None]  # type: ignore[index]


def test_stock_run_names_both_versions_in_its_first_line() -> None:
    head = stock_run._conditions(
        BACKEND, stock_run.datetime.now(), stock_run.STOCK_SET, 6, SPOKEN_PROMPT_1
    )

    assert (head["extraction_prompt"], head["english_extraction_prompt"]) == (
        "spoken-1",
        "first-3",
    )


def test_spoken_run_hands_the_version_named_to_the_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, object]] = []

    def say(*_: object, **named: object) -> object:
        seen.append(named)
        return argparse.Namespace(recorded=None, state=None)

    monkeypatch.setattr(spoken_run, "say", say)
    practice = Path(spoken_run.REPO_ROOT) / "evals/sets/spoken/spoken-r70-practice.json"
    spoken = spoken_run.load_spoken_set(practice)
    ports = spoken_run.Ports(
        model=None,  # type: ignore[arg-type]
        ledger_of=spoken_run.exam_ledger,
        steps=6,
        tuning=DEFAULT_TUNING,
        chinese=SPOKEN_PROMPT_1,
    )

    spoken_run.say_sentence(spoken.sentences[0], spoken, ports)

    assert seen[0]["extract_for_chinese"] is SPOKEN_PROMPT_1
