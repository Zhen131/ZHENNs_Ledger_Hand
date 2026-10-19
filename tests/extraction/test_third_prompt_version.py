"""Tests of the third prompt version: the first prompt with the two rules of the second, no more.

``third`` is built on ``first`` and ``second``: its instructions are the
first prompt's, then the two rules of ``second``, the very same constants;
its examples are the first prompt's ten themselves, with none added; the
words for asking again and the reply table are the first prompt's. It adds
no word that ``second`` does not hold, so the check that ``second``'s added
words hold no test sentence (``test_second_prompt_holds_no_test_sentence``)
covers it, and it has no example of its own to hold to the rules. Every
passage and reply here is invented; nothing is sent to a model.
"""

from __future__ import annotations

from ledger_hand.extraction import prompts
from ledger_hand.extraction.extractor import Extracted
from ledger_hand.extraction.prompting import build_messages
from ledger_hand.extraction.prompts import second, third
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.ports import Role
from tests.extraction.scripted_runs import row, run, table

THIRD = third.THIRD_PROMPT
# The paragraphs said after the first prompt's instructions, in their order.
ADDED_AFTER = (second.BUY_WORDS_RULE, second.U_TOTAL_RULE)
MOST_PARAGRAPHS = 2


def test_the_name_is_the_file_name_and_the_file_says_what_it_holds() -> None:
    assert THIRD.name == "third"
    assert third.__name__ == f"{prompts.__name__}.{THIRD.name}"
    assert third.__doc__


def test_the_instructions_are_the_first_ones_then_the_second_versions_two_rules() -> None:
    assert THIRD.instructions == FIRST_PROMPT.instructions + "".join(ADDED_AFTER)
    assert THIRD.instructions == second.SECOND_PROMPT.instructions
    assert len(ADDED_AFTER) <= MOST_PARAGRAPHS


def test_the_examples_are_the_first_ten_themselves_and_none_more() -> None:
    assert THIRD.examples is FIRST_EXAMPLES
    assert len(THIRD.examples) == len(FIRST_EXAMPLES)


def test_the_words_for_asking_again_and_the_reply_table_are_the_first_prompts() -> None:
    assert THIRD.ask_again == FIRST_PROMPT.ask_again
    # The scripted model of the flow tests routes a call by the identity of its table.
    assert THIRD.reply_table is REPLY_TABLE


def test_the_messages_are_the_instructions_the_first_examples_and_the_passage() -> None:
    messages = build_messages(THIRD, "买了 BTC")
    first = build_messages(FIRST_PROMPT, "买了 BTC")

    assert (messages[0].role, messages[0].content) == (Role.SYSTEM, THIRD.instructions)
    assert messages[1:] == first[1:]


def test_a_reply_to_the_third_version_is_read_as_with_the_first() -> None:
    passage = "今天在OKX补了20U的DOT，均价4.1"
    rows = [row(side="buy", coin="DOT", total="20U", price="4.1", platform="OKX")]

    with_third, model = run(passage, table(*rows), prompt=THIRD)
    with_first, _ = run(passage, table(*rows))

    assert isinstance(with_third, Extracted) and isinstance(with_first, Extracted)
    assert with_third.drafts == with_first.drafts
    assert model.calls[0].reply_schema is REPLY_TABLE
    assert model.calls[0].messages[0].content == THIRD.instructions
