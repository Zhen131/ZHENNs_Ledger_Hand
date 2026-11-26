"""Tests of the ten exam sets said the owner's way: they read, and every gold answer holds.

The ten files sit in a folder of their own, ``evals/sets/spoken/``: a
sentence that waits for the ledger's cash balance (``wait_for``) is one
the program is meant to catch before the model (``cash_question.caught``),
and the gate that no sentence of the sets in ``evals/sets/`` is caught
would take such a sentence for a mistake. The same gate is kept here for
the exam, such sentences left out: no other sentence of the ten files is
caught.

Every check here names a sentence by its identifier only, never by what
was said or by a figure of it, since half the sentences are the hidden
half: a failure shows the list of identifiers found, and nothing else.
No model is called.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from evals.ask_set import load_ask_set
from evals.edit_set import load_edit_set
from evals.exam_book import EXAM_TRADES, exam_ledger
from evals.spoken_set import CANNOT_RECORD, gold_problems, load_spoken_set
from ledger_hand.core.validation import amounts_agree
from ledger_hand.flows.cash_question import caught

SETS = Path(__file__).resolve().parents[2] / "evals" / "sets" / "spoken"
TIERS = ("r100", "r80", "r70")
HALVES = ("practice", "hidden")
# How many sentences each file holds, as the raw material has them.
SIZES = {
    "spoken-r100-practice.json": 15,
    "spoken-r100-hidden.json": 15,
    "spoken-r80-practice.json": 13,
    "spoken-r80-hidden.json": 12,
    "spoken-r70-practice.json": 13,
    "spoken-r70-hidden.json": 12,
    "spoken-asks-practice.json": 6,
    "spoken-asks-hidden.json": 6,
    "spoken-edits-practice.json": 4,
    "spoken-edits-hidden.json": 4,
}


def _entries(name: str) -> list[dict[str, object]]:
    data = json.loads((SETS / name).read_text(encoding="utf-8"))
    if "groups" in data:
        return [entry for group in data["groups"] for entry in group]
    return list(data["sentences"])


def _number(identifier: str) -> int:
    return int(identifier.rsplit("-", 1)[1])


def test_there_are_ten_files_of_the_sizes_the_material_has() -> None:
    assert sorted(path.name for path in SETS.glob("spoken-*.json")) == sorted(SIZES)
    sizes = {name: len(_entries(name)) for name in SIZES}
    assert sizes == SIZES


@pytest.mark.parametrize("name", sorted(SIZES))
def test_each_file_says_its_half_and_the_exam_book(name: str) -> None:
    data = json.loads((SETS / name).read_text(encoding="utf-8"))
    half = "hidden" if "hidden" in name else "practice"
    assert (data["half"], data["book"]) == (half, "exam")


@pytest.mark.parametrize("name", sorted(SIZES))
def test_odd_identifiers_are_practice_and_even_ones_hidden(name: str) -> None:
    practice = "practice" in name
    off = [str(e["id"]) for e in _entries(name) if (_number(str(e["id"])) % 2 == 1) != practice]
    assert off == []


def test_no_sentence_is_in_both_halves_or_twice() -> None:
    seen: dict[str, str] = {}
    twice: list[str] = []
    for name in SIZES:
        for entry in _entries(name):
            text, identifier = str(entry["text"]), str(entry["id"])
            if text in seen:
                twice.append(identifier)
            seen[text] = identifier
    assert twice == []


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("half", HALVES)
def test_every_gold_answer_holds_against_what_was_said(tier: str, half: str) -> None:
    spoken = load_spoken_set(SETS / f"spoken-{tier}-{half}.json")
    assert (spoken.tier, spoken.half) == (tier, half)
    assert gold_problems(spoken) == []


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("half", HALVES)
def test_a_sentence_not_enabled_has_only_cannot_be_recorded(tier: str, half: str) -> None:
    spoken = load_spoken_set(SETS / f"spoken-{tier}-{half}.json")
    off = [
        sentence.id
        for sentence in spoken.sentences
        if not sentence.enabled
        and (sentence.gold.expect != CANNOT_RECORD or sentence.gold.trades or not sentence.wait_for)
    ]
    assert off == []


@pytest.mark.parametrize("half", HALVES)
def test_the_question_and_change_sets_read(half: str) -> None:
    asks = load_ask_set(SETS / f"spoken-asks-{half}.json")
    edits = load_edit_set(SETS / f"spoken-edits-{half}.json")
    assert (asks.book, asks.half, edits.book, edits.half) == ("exam", half, "exam", half)


@pytest.mark.parametrize("half", HALVES)
def test_every_change_names_a_trade_of_the_exam_book_and_amounts_that_agree(half: str) -> None:
    book = dict(EXAM_TRADES)
    off: list[str] = []
    for sentence in load_edit_set(SETS / f"spoken-edits-{half}.json").sentences:
        gold = sentence.gold
        if gold.trade is not None and gold.trade not in book:
            off.append(sentence.id)
        if gold.amounts is not None:
            quantity, price, total = (Decimal(amount) for amount in gold.amounts)
            if not amounts_agree(quantity, price, total):
                off.append(sentence.id)
    assert off == []


def test_no_sentence_of_the_exam_is_caught_as_a_question_about_cash_unless_marked_so() -> None:
    caught_ones: list[str] = []
    for name in SIZES:
        for entry in _entries(name):
            if entry.get("wait_for") == "cash_balance":
                continue
            if caught(str(entry["text"]), exam_ledger()) is not None:
                caught_ones.append(str(entry["id"]))
    assert caught_ones == []
