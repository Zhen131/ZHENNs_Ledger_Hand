"""Which version of the extraction prompt a passage is read with, by whether it holds Chinese.

The assistant extracts a trade from what the user said with one of two
versions. Words with a Chinese character in them, once tidied, go to the
version handed in for Chinese: one whose examples are written the way the
owner speaks. Words with none go to ``first-3``, the version measured on
English, which is never changed for this.

Why: on 2026-11-24 the product owner decided that where the two cannot
both be served, the way he speaks comes first; sentences with Chinese get
examples written his way, and English sentences keep the version they had.

This is the only place that rule lives; the assistant and the measures
that name a version for Chinese all ask it.

Names defined here: ``ENGLISH_EXTRACT_PROMPT`` and ``extract_prompt_for``.
"""

from __future__ import annotations

from ledger_hand.core.chinese import holds_chinese
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3

# The version for words with no Chinese character in them.
ENGLISH_EXTRACT_PROMPT = FIRST_PROMPT_3


def extract_prompt_for(passage: str, chinese: PromptVersion) -> PromptVersion:
    """The version ``passage`` is extracted with: ``chinese`` when it holds a Chinese character.

    ``passage`` is the words as the flow is handed them, already tidied.
    Handed ``first-3`` for Chinese, every passage gets ``first-3``.
    """
    return chinese if holds_chinese(passage) else ENGLISH_EXTRACT_PROMPT
