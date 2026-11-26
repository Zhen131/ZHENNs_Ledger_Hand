"""Gate: the versions for Chinese copy nothing from the exam said the owner's way.

Each version for Chinese adds rules and examples to ``first-3``, written the
way the owner speaks. They may follow how he says things; they may not copy
a sentence of the exam, of the practice half or of the hidden half. What a
version adds (the words of its rules, each new example's passage and its
table) is checked against every sentence of the ten exam files, each as
said and as tidied (``tidy_spoken``), and all through ``tidy_text``. Four
things count as copying:

1. Twelve characters in a row the same.
2. Twenty characters in a row the same once every run of digits and number
   words (with "点" and ".") is written as one "#".
3. A number an example copies (a quantity, a price, a total or a fee, as
   the core reads it), with at least three significant digits, equal to an
   amount in a gold answer of the exam.
4. A whole sentence, or a clause of one, in what the version adds.

Twelve and twenty were measured on the practice half: between two of its
sentences, phrases with no number in them run to about ten characters,
and sentences made from one pattern with other numbers share twenty-five
or more once the numbers are written as "#".

A failure says only which example (or the rules), which half it ran into,
which of the four, and how long: never a sentence, a piece of one or its
number, so that nothing of the hidden half is shown to whoever writes the
examples.

The examples follow the rules every example follows: each field a piece of
its passage, each number and time one the core reads, and each passage
already as tidying writes it.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

from evals.ask_set import load_ask_set
from evals.cells import tidy_text
from evals.edit_set import load_edit_set
from evals.spoken_set import load_spoken_set
from ledger_hand.core.ledger_table import SHARE_UNITS
from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.core.spoken_text import tidy_spoken
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.prompting import Example, PromptVersion, example_reply
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.spoken1 import SPOKEN_PROMPT_1
from ledger_hand.extraction.prompts.spoken2 import SPOKEN_PROMPT_2
from ledger_hand.extraction.reply_table import Field
from tests.extraction.test_new_prompts_hold_no_test_sentence import clauses
from tests.flows.scripted_flow import NOW, ZONE

SETS = Path(__file__).resolve().parents[2] / "evals" / "sets" / "spoken"
RECORDING = ("r100", "r80", "r70")
VERSIONS: tuple[PromptVersion, ...] = (SPOKEN_PROMPT_1, SPOKEN_PROMPT_2)

SAME_IN_A_ROW = 12
SAME_IN_A_ROW_NUMBERS_HIDDEN = 20
FEWEST_SIGNIFICANT_DIGITS = 3

_NUMBER_RUN = re.compile("[0-9零〇一二两三四五六七八九十百千万亿点.]+")
_DIGITS = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)
# The cells of a gold trade that hold an amount.
AMOUNTS = ("quantity", "price", "total", "fee")


def _hidden_numbers(text: str) -> str:
    return _NUMBER_RUN.sub("#", text)


def _exam() -> dict[str, list[tuple[str, str]]]:
    """Each half's sentences, as (said, tidied), and their zone's tidying applied."""
    halves: dict[str, list[tuple[str, str]]] = {"practice": [], "hidden": []}
    for half in halves:
        texts: list[tuple[str, str]] = []
        for tier in RECORDING:
            spoken = load_spoken_set(SETS / f"spoken-{tier}-{half}.json")
            texts += [(one.text, spoken.zone) for one in spoken.sentences]
        asks = load_ask_set(SETS / f"spoken-asks-{half}.json")
        texts += [(one.text, ZONE) for one in asks.sentences]
        edits = load_edit_set(SETS / f"spoken-edits-{half}.json")
        texts += [(one.text, ZONE) for one in edits.sentences]
        halves[half] = [(text, tidy_spoken(text, zone).text) for text, zone in texts]
    return halves


def _gold_numbers() -> dict[str, set[Decimal]]:
    found: dict[str, set[Decimal]] = {"practice": set(), "hidden": set()}
    for half, numbers in found.items():
        for tier in RECORDING:
            spoken = load_spoken_set(SETS / f"spoken-{tier}-{half}.json")
            for sentence in spoken.sentences:
                for trade in sentence.gold.trades:
                    for name in AMOUNTS:
                        cell = trade.cells.get(name)
                        if cell is not None and cell.value is not None:
                            numbers.update(_decimals(cell.value))
    return {half: {n for n in numbers if _significant(n)} for half, numbers in found.items()}


def _decimals(text: str) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for match in _DIGITS.findall(text):
        try:
            numbers.add(Decimal(match))
        except InvalidOperation:
            continue
    return numbers


def _significant(number: Decimal) -> bool:
    return number != 0 and len(number.normalize().as_tuple().digits) >= FEWEST_SIGNIFICANT_DIGITS


def _longest_shared(one: str, other: str) -> int:
    """The length of the longest run of characters ``one`` and ``other`` both hold."""

    def shares(length: int) -> bool:
        runs = {other[i : i + length] for i in range(len(other) - length + 1)}
        return any(one[i : i + length] in runs for i in range(len(one) - length + 1))

    low, high = 0, min(len(one), len(other))
    while low < high:
        middle = (low + high + 1) // 2
        if shares(middle):
            low = middle
        else:
            high = middle - 1
    return low


def _added(version: PromptVersion) -> list[tuple[str, str]]:
    """What ``version`` adds to ``first-3``, each with a label that shows none of it."""
    base = FIRST_PROMPT_3.instructions
    rules = version.instructions.removeprefix(base)
    added = [("the rules", rules)] if rules else []
    for number, example in enumerate(_new_examples(version), start=1):
        added.append((f"example {number}, its passage", example.passage))
        added.append((f"example {number}, its table", example_reply(example)))
    return added


def _new_examples(version: PromptVersion) -> tuple[Example, ...]:
    return tuple(one for one in version.examples if one not in FIRST_PROMPT_3.examples)


def _example_numbers(example: Example) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for row in example.rows:
        allowed = (*SHARE_UNITS, *(row[f] for f in (Field.COIN, Field.FEE_CURRENCY) if f in row))
        for field in _NUMBER_FIELDS:
            if row.get(field):
                read = read_number(row[field], allowed)
                if isinstance(read, Recognised):
                    numbers.add(read.value)
    return numbers


EXAM = _exam()


@pytest.mark.parametrize("version", VERSIONS, ids=lambda version: version.name)
def test_nothing_a_version_adds_copies_a_sentence_of_the_exam(version: PromptVersion) -> None:
    copied: list[tuple[str, str, str, int]] = []
    for label, text in _added(version):
        mine = tidy_text(text)
        for half, sentences in EXAM.items():
            longest = longest_hidden = 0
            whole = False
            for said, tidied in sentences:
                for form in (tidy_text(said), tidy_text(tidied)):
                    longest = max(longest, _longest_shared(mine, form))
                    longest_hidden = max(
                        longest_hidden,
                        _longest_shared(_hidden_numbers(mine), _hidden_numbers(form)),
                    )
                pieces = [tidy_text(said), tidy_text(tidied), *clauses(said), *clauses(tidied)]
                whole = whole or any(piece and piece in mine for piece in pieces)
            if longest >= SAME_IN_A_ROW:
                copied.append((label, half, "characters in a row", longest))
            if longest_hidden >= SAME_IN_A_ROW_NUMBERS_HIDDEN:
                copied.append((label, half, "characters in a row, numbers as #", longest_hidden))
            if whole:
                copied.append((label, half, "a whole sentence or clause", 0))

    assert copied == []


@pytest.mark.parametrize("version", VERSIONS, ids=lambda version: version.name)
def test_no_number_of_an_example_is_a_number_of_the_exam(version: PromptVersion) -> None:
    exam = _gold_numbers()
    same = [
        (f"example {number}", half, "a number of the exam", 0)
        for number, example in enumerate(_new_examples(version), start=1)
        for half, numbers in exam.items()
        if {n for n in _example_numbers(example) if _significant(n)} & numbers
    ]

    assert same == []


def test_the_twelve_and_the_twenty_are_the_numbers_written_above() -> None:
    assert (SAME_IN_A_ROW, SAME_IN_A_ROW_NUMBERS_HIDDEN, FEWEST_SIGNIFICANT_DIGITS) == (12, 20, 3)


def _examples() -> list[tuple[str, Example]]:
    return [
        (f"{version.name} example {number}", example)
        for version in VERSIONS
        for number, example in enumerate(_new_examples(version), start=1)
    ]


@pytest.mark.parametrize(("name", "example"), _examples(), ids=[n for n, _ in _examples()])
def test_every_example_is_already_tidied(name: str, example: Example) -> None:
    assert tidy_spoken(example.passage, ZONE).text == example.passage, name


@pytest.mark.parametrize(("name", "example"), _examples(), ids=[n for n, _ in _examples()])
def test_every_example_is_copied_from_its_passage_and_read_by_the_core(
    name: str, example: Example
) -> None:
    passage = Passage(example.passage)
    for row in example.rows:
        for field, text in row.items():
            if field is Field.SIDE or not text:
                continue
            found = passage.find(text)
            assert isinstance(found, Piece) and found.text == text, (name, field, text)
        allowed = (*SHARE_UNITS, *(row[f] for f in (Field.COIN, Field.FEE_CURRENCY) if f in row))
        for field in _NUMBER_FIELDS:
            if row.get(field):
                assert isinstance(read_number(row[field], allowed), Recognised), (name, field)
        if row.get(Field.TIME):
            assert isinstance(read_time(row[Field.TIME], NOW, ZONE), TimeRecognised), name


def test_each_version_keeps_every_word_and_example_of_the_third_version() -> None:
    for version in VERSIONS:
        assert version.instructions.startswith(FIRST_PROMPT_3.instructions)
        assert version.examples[: len(FIRST_PROMPT_3.examples)] == FIRST_PROMPT_3.examples
        assert version.ask_again == FIRST_PROMPT_3.ask_again
