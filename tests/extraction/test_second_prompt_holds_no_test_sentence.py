"""The words the second prompt version adds hold no test sentence, nor any clause of one.

The test sentences measure how well the model reads passages it has not
seen; words in a prompt that held one of them, or a clause of one, would
teach the model the answer. The words the second version adds to the first
are checked here: its two rules, and its own examples, their passages and
their replies. They are checked against every sentence of the four sets
(debug, final, writings, voice) and the four smoke passages, as a whole and
in every clause of ``SHORTEST_CLAUSE`` characters or more, after the tidying
the scoring uses. For the final set a finding names the sentence only, never
its words.

A clause of the voice set is also looked for with every number and every
coin name in it, and in the added words, put as one mark each, so that a
clause copied with only its numbers or its coin changed is found too.
Nothing here sends anything to a model.
"""

from __future__ import annotations

import re

import pytest

from evals.cells import tidy_text
from evals.gold import DEBUG_SET, FINAL_SET, Sentence, Split, load_set
from evals.voice import VOICE_SET
from evals.writings import WRITINGS_SET
from ledger_hand.core.coins import BUILT_IN_COINS
from ledger_hand.extraction.prompting import example_reply
from ledger_hand.extraction.prompts import second
from ledger_hand.extraction.prompts.second_examples import OWNER_EXAMPLES
from tests.live.test_live_extraction import PASSAGES as SMOKE_PASSAGES

SETS = {
    Split.DEBUG: load_set(DEBUG_SET, Split.DEBUG),
    Split.FINAL: load_set(FINAL_SET, Split.FINAL),
    Split.WRITINGS: load_set(WRITINGS_SET, Split.WRITINGS),
    Split.VOICE: load_set(VOICE_SET, Split.VOICE),
}
SMOKE = [str(param.values[0]) for param in SMOKE_PASSAGES]
# Shorter pieces ("0.5 ETH", "昨天") are everyday words, not a sentence's own.
SHORTEST_CLAUSE = 8
_CLAUSE_ENDS = re.compile(r"[，,；;。.!！?？:：]")
# A number, with the points, commas and colons inside it, and the mark it is put as.
_NUMBER = re.compile(r"\d+(?:[.,:]\d+)*")
NUMBER_MARK = "#"
COIN_MARK = "@"
_LATIN = re.compile(r"[A-Za-z]")


def added_words() -> str:
    """Every word the second version says that the first does not."""
    texts = [second.BUY_WORDS_RULE, second.U_TOTAL_RULE]
    texts += [example.passage for example in OWNER_EXAMPLES]
    texts += [example_reply(example) for example in OWNER_EXAMPLES]
    return "\n".join(texts)


def clauses(text: str) -> list[str]:
    return [
        piece
        for piece in (tidy_text(part) for part in _CLAUSE_ENDS.split(text))
        if len(piece) >= SHORTEST_CLAUSE
    ]


def pieces(text: str) -> list[str]:
    """The whole of ``text``, tidied, and every clause of it long enough to count."""
    return [tidy_text(text), *clauses(text)]


def _coin_pattern() -> re.Pattern[str]:
    names = {form for coin in BUILT_IN_COINS for form in (coin.symbol, coin.name, *coin.aliases)}
    shapes = []
    for name in sorted(names, key=len, reverse=True):
        shape = re.escape(name)
        # A Latin name counts only on its own, never as part of a longer word.
        shapes.append(rf"(?<![A-Za-z]){shape}(?![A-Za-z])" if _LATIN.search(name) else shape)
    return re.compile("|".join(shapes), re.IGNORECASE)


_COIN = _coin_pattern()


def marked(text: str) -> str:
    """``text``, tidied, with every number and every coin name put as one mark each."""
    return _COIN.sub(COIN_MARK, _NUMBER.sub(NUMBER_MARK, tidy_text(text)))


def found_in(sentences: tuple[Sentence, ...], text: str) -> list[str]:
    """The ids of the sentences of which a whole or a clause stands in ``text``."""
    tidied = tidy_text(text)
    return [s.id for s in sentences if any(piece in tidied for piece in pieces(s.text))]


@pytest.mark.parametrize("split", [Split.DEBUG, Split.WRITINGS, Split.VOICE])
def test_no_sentence_nor_any_of_its_clauses_is_in_the_added_words(split: Split) -> None:
    text = tidy_text(added_words())
    found = [
        (sentence.id, piece)
        for sentence in SETS[split]
        for piece in pieces(sentence.text)
        if piece in text
    ]

    assert found == []


def test_no_final_sentence_nor_any_of_its_clauses_is_in_the_added_words() -> None:
    # Only the ids are said: the final set's words are kept out of sight.
    assert found_in(SETS[Split.FINAL], added_words()) == []


def test_no_smoke_passage_nor_any_of_its_clauses_is_in_the_added_words() -> None:
    text = tidy_text(added_words())

    assert [piece for passage in SMOKE for piece in pieces(passage) if piece in text] == []


def marked_clauses(text: str) -> list[str]:
    """The clauses of ``text`` long enough to count once its numbers and coins are marks."""
    return [
        piece
        for piece in (tidy_text(part) for part in _CLAUSE_ENDS.split(marked(text)))
        if len(piece) >= SHORTEST_CLAUSE
    ]


def test_no_voice_clause_is_in_the_added_words_with_only_its_numbers_or_coins_changed() -> None:
    text = marked(added_words())
    found = [
        (sentence.id, piece)
        for sentence in SETS[Split.VOICE]
        for piece in marked_clauses(sentence.text)
        if piece in text
    ]

    assert found == []


def test_the_check_finds_a_clause_planted_in_the_added_words() -> None:
    sentence = SETS[Split.VOICE][0]
    planted = "Some words. " + clauses(sentence.text)[0] + " More words."

    assert found_in((sentence,), planted) == [sentence.id]
    assert found_in((sentence,), "Some words.") == []


def test_the_marked_check_finds_a_clause_planted_with_other_numbers_and_another_coin() -> None:
    clause = "今天在OKX用30USDT补了一点ADA的仓位"
    changed = "今天在OKX用45.5USDT补了一点SOL的仓位"

    assert marked(clause) == marked(changed)
    assert marked_clauses(clause)[0] in marked("前面的话，" + changed + "，后面的话")
    assert marked("Unit price") == "Unit price"
