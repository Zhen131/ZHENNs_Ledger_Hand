"""The second prompt that picks an asset from the ledger's list: a product is not its maker.

Measured on the practice half of the names set, the first version
(``asset_pick``) took a soft drink's name for a listed company that makes
another drink. This version keeps the first one's words and examples, adds
a sentence that a product or a brand is not its maker's share, and one
example that answers so with an empty code: a drink of a listed company.
The examples still name no company, product or coin of any measure of
this program.

A version is never changed once it has been measured; a change of wording
or of an example is a new version in a new file.

This version is named ``asset-pick-2``.

Names defined here: ``ASSET_PICK_PROMPT_2``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompts.asset_pick import (
    ASSET_PICK_PROMPT,
    AssetPickPrompt,
    PickExample,
)

_INSTRUCTIONS = ASSET_PICK_PROMPT.instructions.replace(
    "Never pick an asset only because its name looks or sounds like the words.",
    "A product, a drink or a brand that a company sells is not that company's share, "
    "unless the words are the company's own name. "
    "Never pick an asset only because its name looks or sounds like the words.",
)

_LIST = ASSET_PICK_PROMPT.examples[0].listing

_EXAMPLES = (
    *ASSET_PICK_PROMPT.examples,
    PickExample(words="星冰乐", listing=_LIST, said="星冰乐", code=""),
)

ASSET_PICK_PROMPT_2 = AssetPickPrompt(
    name="asset-pick-2", instructions=_INSTRUCTIONS, examples=_EXAMPLES
)
