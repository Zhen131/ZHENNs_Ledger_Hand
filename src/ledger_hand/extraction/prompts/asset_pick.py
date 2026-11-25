"""The first prompt that picks, from the ledger's list, the asset a name not found names.

The technique is a closed choice with a few examples: the model is handed
only the words the user used for the asset (as extraction copied them,
never the rest of the passage) and the ledger's list of the assets that
can be traded, one a line as code, name and kind. It copies the part of
the words that names the asset and gives one code of the list, or an empty
code when the list does not hold what is meant. The examples are shown as
earlier turns of the conversation: each its words and list, said by the
user, and its reply, written by the model. They name companies and coins
that no measure of this program uses, and one of them answers with an
empty code.

The program checks every reply (``extraction.asset_picking``); a code the
list lacks, words the user did not say, or words left over that are more
than the asset's name are never taken.

A version is never changed once it has been measured; a change of wording
or of an example is a new version in a new file.

This version is named ``asset-pick-1``.

Names defined here: ``AssetPickPrompt``, ``PickExample``, ``ListedAsset``,
``listing_text`` and ``ASSET_PICK_PROMPT``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListedAsset:
    """One asset of the list the model chooses from: its code, its name and its kind."""

    code: str
    name: str
    kind: str


@dataclass(frozen=True)
class PickExample:
    """An invented choice: the words, the list, and the reply the model should write."""

    words: str
    listing: tuple[ListedAsset, ...]
    said: str
    code: str


@dataclass(frozen=True)
class AssetPickPrompt:
    """One version of the prompt: its name, its instructions and its examples."""

    name: str
    instructions: str
    examples: tuple[PickExample, ...]


def listing_text(words: str, listing: tuple[ListedAsset, ...]) -> str:
    """What the model is handed: the words, then the list, one asset a line."""
    lines = [f"Words: {words}", "List:"]
    lines.extend(f"{asset.code} | {asset.name} | {asset.kind}" for asset in listing)
    return "\n".join(lines)


_INSTRUCTIONS = """\
You match the words one person used for an asset they bought or sold to one \
asset of their own ledger. You are given the words, and the list of the \
assets in the ledger: one a line, its code, its name in the ledger and its \
kind (stock, crypto or other). People often say a company or a coin by its \
Chinese name, by its English name, or by a common short name.

Reply with one JSON object: {"said": "...", "code": "..."}.

- "said": the part of the words that names the asset, copied character for \
character.
- "code": the code of the one asset of the list those words name. Write "" \
when the list does not hold it, when the words name more than one asset, or \
when they name something other than the asset itself, such as an option, a \
future, a fund or another company.

Never pick an asset only because its name looks or sounds like the words. \
When you are not sure, write "" for the code.
"""

_LIST = (
    ListedAsset("PG", "Procter & Gamble", "stock"),
    ListedAsset("SBUX", "Starbucks", "stock"),
    ListedAsset("BA", "Boeing", "stock"),
    ListedAsset("LINK", "Chainlink", "crypto"),
)

_EXAMPLES = (
    PickExample(words="宝洁", listing=_LIST, said="宝洁", code="PG"),
    PickExample(words="星巴克公司", listing=_LIST, said="星巴克", code="SBUX"),
    PickExample(words="BOEING SHARES", listing=_LIST, said="BOEING", code="BA"),
    PickExample(words="麦当劳", listing=_LIST, said="麦当劳", code=""),
    PickExample(words="波音的期权", listing=_LIST, said="波音的期权", code=""),
)

ASSET_PICK_PROMPT = AssetPickPrompt(
    name="asset-pick-1", instructions=_INSTRUCTIONS, examples=_EXAMPLES
)
