"""The third prompt that picks an asset from the ledger's list: only the asset's own name.

Measured on the practice half of the names set, the second version
(``asset_pick2``) still took a soft drink's name for a listed company. This
version says, before the rules of the reply, that only the asset's own name
(its name as listed, a translation of it, or its well-known short name) is
matched, and that a product or brand is never, not even of a company on the
list; and it adds one more example of a listed company's product answered
with an empty code. The examples still name no company, product or coin of
any measure of this program.

A version is never changed once it has been measured; a change of wording
or of an example is a new version in a new file.

This version is named ``asset-pick-3``.

Names defined here: ``ASSET_PICK_PROMPT_3``.
"""

from __future__ import annotations

from ledger_hand.extraction.prompts.asset_pick import AssetPickPrompt, PickExample
from ledger_hand.extraction.prompts.asset_pick2 import ASSET_PICK_PROMPT_2

_INSTRUCTIONS = ASSET_PICK_PROMPT_2.instructions.replace(
    'Reply with one JSON object: {"said": "...", "code": "..."}.',
    "Match only the asset's own name: its name as listed, a translation of that name, "
    "or its well-known short name. The name of a product, a drink or a brand is never "
    "a match, not even when the company that sells it is on the list.\n\n"
    'Reply with one JSON object: {"said": "...", "code": "..."}.',
)

_LIST = ASSET_PICK_PROMPT_2.examples[0].listing

_EXAMPLES = (
    *ASSET_PICK_PROMPT_2.examples,
    PickExample(words="汰渍", listing=_LIST, said="汰渍", code=""),
)

ASSET_PICK_PROMPT_3 = AssetPickPrompt(
    name="asset-pick-3", instructions=_INSTRUCTIONS, examples=_EXAMPLES
)
