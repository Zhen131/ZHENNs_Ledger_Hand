"""Tests of the names set and its judging: the set as written, and each verdict.

Nothing here touches a model.
"""

from __future__ import annotations

from collections import Counter

import pytest

from evals.name_set import Group, Half, NameSentence, Verdict, judge, load_name_set
from ledger_hand.ledger.demo_book import DEMO_ASSETS

NAMES = load_name_set()


def test_each_group_has_enough_sentences_split_into_two_halves_by_number() -> None:
    groups = Counter(sentence.group for sentence in NAMES.sentences)

    assert groups[Group.ON_LIST] >= 15
    assert groups[Group.OFF_LIST] >= 20
    for sentence in NAMES.sentences:
        number = int(sentence.id[1:])
        assert sentence.half is (Half.PRACTICE if number % 2 else Half.LOCKED)


def test_names_alike_and_names_with_more_words_fall_into_both_halves() -> None:
    for kind in ("similar_name", "qualified"):
        halves = Counter(sentence.half for sentence in NAMES.sentences if sentence.kind == kind)
        assert halves[Half.PRACTICE] == halves[Half.LOCKED] > 0


def test_every_gold_code_is_an_asset_of_the_demo_book_and_its_words_are_in_the_sentence() -> None:
    codes = {asset.code for asset in DEMO_ASSETS}

    for sentence in NAMES.sentences:
        assert sentence.words in sentence.text
        if sentence.gold is not None:
            assert sentence.gold in codes


def one(group: Group, gold: str | None) -> NameSentence:
    return NameSentence("T1", group, "on_list", Half.PRACTICE, "text", "words", gold)


@pytest.mark.parametrize(
    ("found", "verdict"),
    [
        ({"MSFT"}, Verdict.RIGHT),
        (set(), Verdict.NOT_MATCHED),
        ({"AAPL"}, Verdict.WRONG),
        ({"MSFT", "INTC"}, Verdict.WRONG),
    ],
)
def test_on_the_list(found: set[str], verdict: Verdict) -> None:
    assert judge(one(Group.ON_LIST, "MSFT"), found) is verdict


@pytest.mark.parametrize(("found", "verdict"), [(set(), Verdict.RIGHT), ({"KO"}, Verdict.WRONG)])
def test_off_the_list(found: set[str], verdict: Verdict) -> None:
    assert judge(one(Group.OFF_LIST, None), found) is verdict
