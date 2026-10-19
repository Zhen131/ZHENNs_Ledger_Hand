"""The words the fourth prompt version adds hold no test sentence, nor any clause of one.

The test sentences measure how well the model reads passages it has not
seen; words in a prompt that held one of them, or a clause of one, would
teach the model the answer. The words the fourth version adds to the first
are checked here: the two rules it takes from ``second``, and its own
examples, their passages and their replies. They are checked against every
sentence of the four sets (debug, final, writings, voice) and the four smoke
passages, as a whole and in every clause of ``SHORTEST_CLAUSE`` characters
or more, after the tidying the scoring uses. For the final set a finding
names the sentence only, never its words.

A clause of the voice set is also looked for with every number in it, in
digits or in Chinese numbers, and every coin name, and in the added words,
put as one mark each, so that a clause copied with only its numbers or its
coin changed is found too. Every helper here reads the words of ``fourth``.
Nothing here sends anything to a model.
"""

from __future__ import annotations

import re

import pytest

from evals.cells import tidy_text
from evals.gold import Sentence, Split
from ledger_hand.extraction.prompting import example_reply
from ledger_hand.extraction.prompts import second
from ledger_hand.extraction.prompts.fourth_examples import ADDED_EXAMPLES
from tests.extraction.test_second_prompt_holds_no_test_sentence import (
    _CLAUSE_ENDS,
    _COIN,
    COIN_MARK,
    NUMBER_MARK,
    SETS,
    SHORTEST_CLAUSE,
    SMOKE,
    clauses,
    found_in,
    pieces,
)

# A number in digits, with the points, commas and colons inside it, or a run of two
# Chinese numbers or more ("两千四", "六万三千五"); a single one, as in "一个", is a word.
_FIGURES = re.compile(r"\d+(?:[.,:]\d+)*|[零一二两三四五六七八九十百千万亿]{2,}")


def added_words() -> str:
    """Every word the fourth version says that the first does not."""
    texts = [second.BUY_WORDS_RULE, second.U_TOTAL_RULE]
    texts += [example.passage for example in ADDED_EXAMPLES]
    texts += [example_reply(example) for example in ADDED_EXAMPLES]
    return "\n".join(texts)


def findings(sentences: tuple[Sentence, ...], text: str) -> list[tuple[str, str]]:
    """Each sentence, with the whole or the clause of it, that stands in ``text``."""
    tidied = tidy_text(text)
    return [(s.id, piece) for s in sentences for piece in pieces(s.text) if piece in tidied]


def figures_marked(text: str) -> str:
    """``text``, tidied, with every number, in digits or Chinese, and every coin as one mark."""
    return _COIN.sub(COIN_MARK, _FIGURES.sub(NUMBER_MARK, tidy_text(text)))


def figures_marked_clauses(text: str) -> list[str]:
    """The clauses of ``text`` long enough to count once its numbers and coins are marks."""
    return [
        piece
        for piece in (tidy_text(part) for part in _CLAUSE_ENDS.split(figures_marked(text)))
        if len(piece) >= SHORTEST_CLAUSE
    ]


def marked_findings(sentences: tuple[Sentence, ...], text: str) -> list[tuple[str, str]]:
    marked = figures_marked(text)
    return [
        (s.id, piece)
        for s in sentences
        for piece in figures_marked_clauses(s.text)
        if piece in marked
    ]


@pytest.mark.parametrize("split", [Split.DEBUG, Split.WRITINGS, Split.VOICE])
def test_no_sentence_nor_any_of_its_clauses_is_in_the_added_words(split: Split) -> None:
    assert findings(SETS[split], added_words()) == []


def test_no_final_sentence_nor_any_of_its_clauses_is_in_the_added_words() -> None:
    # Only the ids are said: the final set's words are kept out of sight.
    assert found_in(SETS[Split.FINAL], added_words()) == []


def test_no_smoke_passage_nor_any_of_its_clauses_is_in_the_added_words() -> None:
    text = tidy_text(added_words())

    assert [piece for passage in SMOKE for piece in pieces(passage) if piece in text] == []


def test_no_voice_clause_is_in_the_added_words_with_only_its_numbers_or_coins_changed() -> None:
    assert marked_findings(SETS[Split.VOICE], added_words()) == []


def test_the_check_finds_a_sentence_or_a_clause_planted_in_the_added_words() -> None:
    sentence = SETS[Split.DEBUG][0]
    clause = clauses(sentence.text)[0]

    assert findings((sentence,), "Some words. " + clause + " More words.") == [
        (sentence.id, clause)
    ]
    assert (sentence.id, tidy_text(sentence.text)) in findings((sentence,), sentence.text)
    assert findings((sentence,), "Some words.") == []


def test_the_marked_check_finds_a_clause_planted_with_other_numbers_and_another_coin() -> None:
    sentence = SETS[Split.VOICE][0]
    clause = "今天在OKX用30USDT补了一点ADA的仓位"
    changed = "今天在OKX用45.5USDT补了一点SOL的仓位"

    assert figures_marked(clause) == figures_marked(changed)
    assert figures_marked_clauses(clause)[0] in figures_marked(
        "前面的话，" + changed + "，后面的话"
    )
    planted = sentence.text.replace("ADA", "SOL")
    assert marked_findings((sentence,), planted)


def test_the_marked_check_puts_chinese_numbers_as_one_mark_but_not_a_single_one() -> None:
    assert figures_marked("价格两千四先拿着") == figures_marked("价格六万三千五先拿着")
    assert figures_marked("价格两千四先拿着") == figures_marked("价格2,450先拿着")
    assert figures_marked("0.314一个") == f"{NUMBER_MARK}一个"
    assert figures_marked("Unit price") == "Unit price"
