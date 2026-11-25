"""Gate: the catch of a question about cash, tried on every sentence the repository holds.

No model is called. The eight sentences named for it must all be caught.
None of the sentences near them (``must_pass``), and none of every
sentence and passage of the other sets, the demo sentences among them,
may be caught: one caught would no longer reach the model, so the line is
zero. When one is, the word list is mended, never the sentence.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from evals.cash_run import CASH_SET, load_cash_set
from ledger_hand.flows.cash_question import caught
from ledger_hand.ledger.fake_ledger import FakeLedger

REPO = Path(__file__).resolve().parents[2]
SETS = sorted(path for path in (REPO / "evals" / "sets").glob("*.json") if path != CASH_SET)
DEMO = REPO / "tests" / "live" / "demo_sentences.json"
_, _, SENTENCES = load_cash_set()


def _texts(value: object, key: str = "") -> Iterator[str]:
    """Every sentence in a set file: each text under "text" or "said", however deep."""
    if isinstance(value, dict):
        for name, inner in value.items():
            yield from _texts(inner, name)
    elif isinstance(value, list):
        for inner in value:
            yield from _texts(inner, key)
    elif isinstance(value, str) and key in {"text", "said"}:
        yield value


def every_other_sentence() -> list[tuple[str, str]]:
    found = []
    for path in (*SETS, DEMO):
        data = json.loads(path.read_text(encoding="utf-8"))
        found += [(path.name, text) for text in _texts(data)]
    return found


def test_the_sets_hold_the_sentences_looked_for() -> None:
    names = {name for name, _ in every_other_sentence()}
    expected = {"debug.json", "final.json", "tools.json", "asks.json", "demo_sentences.json"}
    assert expected <= names
    assert len(every_other_sentence()) > 150


@pytest.mark.parametrize(
    "sentence", [one for one in SENTENCES if one.group == "named"], ids=lambda one: one.id
)
def test_each_named_question_about_cash_is_caught(sentence) -> None:  # type: ignore[no-untyped-def]
    assert caught(sentence.text, FakeLedger()) is not None


def test_eight_are_named_and_at_least_twelve_must_pass_half_in_each_language() -> None:
    named = [one for one in SENTENCES if one.group == "named"]
    passing = [one for one in SENTENCES if one.group == "must_pass"]
    chinese = [one for one in passing if any("一" <= c <= "鿿" for c in one.text)]
    assert len(named) == 8
    assert len(passing) >= 12
    assert len(chinese) * 2 == len(passing)


def test_none_of_the_sentences_near_them_is_caught() -> None:
    caught_ones = [
        (one.id, one.text)
        for one in SENTENCES
        if one.group == "must_pass" and caught(one.text, FakeLedger()) is not None
    ]
    assert caught_ones == []


def test_no_sentence_of_any_other_set_nor_any_demo_sentence_is_caught() -> None:
    caught_ones = [
        (name, text)
        for name, text in every_other_sentence()
        if caught(text, FakeLedger()) is not None
    ]
    assert caught_ones == []
