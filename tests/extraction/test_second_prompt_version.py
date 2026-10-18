"""Tests of the second prompt version: the first prompt with two named rules and more examples.

``second`` is built on ``first`` and changes two things: two rules said after
the first prompt's instructions, each a named constant, and examples added
after the first prompt's ten. Everything else is the first prompt's, the
very same text and objects: its instructions before the rules, its ten
examples in their order, the words for asking again and the reply table.
Every passage and reply here is invented; nothing is sent to a model.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction import prompts
from ledger_hand.extraction.extractor import Extracted
from ledger_hand.extraction.prompting import build_messages, example_reply
from ledger_hand.extraction.prompts import second, second_examples
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.ports import Role
from tests.extraction.scripted_runs import row, run, table

SECOND = second.SECOND_PROMPT
# The paragraphs said after the first prompt's instructions, in their order.
ADDED_AFTER = (second.BUY_WORDS_RULE, second.U_TOTAL_RULE)
# At most two paragraphs and ten examples more than the first prompt.
MOST_PARAGRAPHS = 2
MOST_EXAMPLES = 10
SELL_WORDS = ("卖", "止盈", "清仓", "sell", "sold")


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_name_is_the_file_name_and_each_file_says_what_it_holds() -> None:
    assert SECOND.name == "second"
    assert second.__name__ == f"{prompts.__name__}.{SECOND.name}"
    assert second_examples.__name__ == f"{prompts.__name__}.second_examples"
    assert second.__doc__ and second_examples.__doc__


def test_the_instructions_are_the_first_ones_then_the_declared_rules_and_nothing_else() -> None:
    assert SECOND.instructions == FIRST_PROMPT.instructions + "".join(ADDED_AFTER)
    assert SECOND.instructions.startswith(FIRST_PROMPT.instructions)
    assert len(ADDED_AFTER) <= MOST_PARAGRAPHS
    assert all(paragraph.endswith("\n") and paragraph.strip() for paragraph in ADDED_AFTER)


def test_the_first_rule_names_the_owners_words_for_a_buy_and_no_word_for_a_sell() -> None:
    rule = flat(second.BUY_WORDS_RULE)

    assert rule.startswith("6. ")
    for word in ("补", "补了", "再补", "补仓", "买到", "买了点"):
        assert word in rule
    assert '"side" "buy"' in rule
    for word in SELL_WORDS:
        assert word not in rule


def test_the_second_rule_makes_an_amount_in_u_the_total_unless_said_as_the_fee_or_price() -> None:
    rule = flat(second.U_TOTAL_RULE)

    assert rule.startswith("7. A number with U or USDT written right after it")
    assert "no 个 and no coin name beside it" in rule
    assert "is the whole amount paid" in rule
    for said in ("手续费", "fee", "单价", "一个", "@"):
        assert said in rule
    assert "never into quantity or fee" in rule


def test_the_examples_are_the_first_ten_themselves_then_the_new_ones() -> None:
    first_count = len(FIRST_EXAMPLES)

    assert SECOND.examples is second_examples.SECOND_EXAMPLES
    assert SECOND.examples[:first_count] == FIRST_EXAMPLES
    for given, own in zip(SECOND.examples[:first_count], FIRST_EXAMPLES, strict=True):
        assert given is own
    assert SECOND.examples[first_count:] == second_examples.OWNER_EXAMPLES
    assert 1 <= len(second_examples.OWNER_EXAMPLES) <= MOST_EXAMPLES


def test_the_words_for_asking_again_are_the_first_prompts() -> None:
    assert SECOND.ask_again == FIRST_PROMPT.ask_again


def test_the_reply_table_is_the_shared_table_itself() -> None:
    # The scripted model of the flow tests routes a call by the identity of its table.
    assert SECOND.reply_table is REPLY_TABLE
    assert SECOND.reply_table is FIRST_PROMPT.reply_table


def test_the_messages_are_the_instructions_every_example_in_order_and_the_passage() -> None:
    messages = build_messages(SECOND, "买了 BTC")

    assert (messages[0].role, messages[0].content) == (Role.SYSTEM, SECOND.instructions)
    pairs = messages[1:-1]
    assert len(pairs) == 2 * len(SECOND.examples)
    for index, example in enumerate(SECOND.examples):
        said, written = pairs[2 * index], pairs[2 * index + 1]
        assert (said.role, said.content) == (Role.USER, example.passage)
        assert (written.role, written.content) == (Role.ASSISTANT, example_reply(example))
    assert (messages[-1].role, messages[-1].content) == (Role.USER, "买了 BTC")


@pytest.mark.parametrize("passage", ["今天在OKX补了20U的DOT，均价4.1", "Bought 2 SOL at 150 today"])
def test_a_reply_to_the_second_version_is_read_as_with_the_first(passage: str) -> None:
    rows = [row(side="buy", coin="DOT", total="20U", price="4.1", platform="OKX")]
    if passage.startswith("Bought"):
        rows = [row(side="buy", coin="SOL", quantity="2 SOL", price="150", time="today")]

    with_second, model = run(passage, table(*rows), prompt=SECOND)
    with_first, _ = run(passage, table(*rows))

    assert isinstance(with_second, Extracted) and isinstance(with_first, Extracted)
    assert with_second.drafts == with_first.drafts
    assert with_second.issues == with_first.issues
    assert model.calls[0].reply_schema is REPLY_TABLE
    assert model.calls[0].messages[0].content == SECOND.instructions
