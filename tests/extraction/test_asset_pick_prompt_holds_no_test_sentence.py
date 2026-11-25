"""The prompt that picks an asset holds no sentence and no name of the sets it is measured on.

The names set measures how well the model picks an asset for names it has
not seen; a prompt that held one of its names, or a sentence of it, would
teach the model the answer. Checked against the names set (every sentence,
and every name of an asset in it) and against the debug and final sets of
extraction (every sentence, and every clause of eight characters or more),
after the same tidying the scoring uses. Nothing here sends anything to a
model.
"""

from __future__ import annotations

import json

import pytest

from evals.cells import tidy_text
from evals.name_set import load_name_set
from ledger_hand.extraction.prompts.asset_pick import ASSET_PICK_PROMPT, AssetPickPrompt
from ledger_hand.extraction.prompts.asset_pick2 import ASSET_PICK_PROMPT_2
from tests.extraction.test_new_prompts_hold_no_test_sentence import SENTENCES, clauses

PICK_PROMPTS = [ASSET_PICK_PROMPT, ASSET_PICK_PROMPT_2]
NAMES = load_name_set()
# The names of the set's assets, and the bare names inside them.
NAME_WORDS = sorted(
    {sentence.words for sentence in NAMES.sentences}
    | {
        "微软",
        "英特尔",
        "可口可乐",
        "苹果",
        "英伟达",
        "百事",
        "雪碧",
        "英飞凌",
        "微博",
        "以太坊",
        "比特币",
        "微策略",
        "特斯拉",
        "谷歌",
        "茅台",
        "亚马逊",
        "腾讯",
        "阿里巴巴",
        "狗狗币",
        "柚子币",
        "波卡",
        "Microsoft",
        "Intel",
        "Coca",
        "Apple",
        "NVIDIA",
        "Pepsi",
    }
)


def text_of(prompt: AssetPickPrompt) -> str:
    examples = [
        json.dumps([one.words, one.said, one.code, [str(asset) for asset in one.listing]])
        for one in prompt.examples
    ]
    return tidy_text("\n".join([prompt.instructions, *examples]))


@pytest.mark.parametrize("prompt", PICK_PROMPTS, ids=lambda prompt: prompt.name)
def test_no_name_of_the_names_set_is_in_the_prompt(prompt: AssetPickPrompt) -> None:
    text = text_of(prompt).casefold()

    assert [word for word in NAME_WORDS if tidy_text(word).casefold() in text] == []


@pytest.mark.parametrize("prompt", PICK_PROMPTS, ids=lambda prompt: prompt.name)
def test_no_sentence_of_the_names_set_is_in_the_prompt(prompt: AssetPickPrompt) -> None:
    text = text_of(prompt)

    assert [one.id for one in NAMES.sentences if tidy_text(one.text) in text] == []


@pytest.mark.parametrize("prompt", PICK_PROMPTS, ids=lambda prompt: prompt.name)
def test_no_sentence_of_the_debug_and_final_sets_nor_any_clause_is_in_the_prompt(
    prompt: AssetPickPrompt,
) -> None:
    text = text_of(prompt)
    found = [
        (sentence.id, piece)
        for sentence in SENTENCES
        for piece in [tidy_text(sentence.text), *clauses(sentence.text)]
        if piece in text
    ]

    assert found == []


def test_each_prompt_has_an_example_that_answers_with_no_code() -> None:
    for prompt in PICK_PROMPTS:
        assert any(example.code == "" for example in prompt.examples)
