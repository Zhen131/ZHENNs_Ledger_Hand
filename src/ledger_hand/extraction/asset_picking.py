"""Picking, from the ledger's list, the asset a name the program does not know names.

The asset table finds an asset only by a name it holds whole: its code, its
name in the ledger, or a name the built-in coin table lends it. "微软的股票"
is none of these for MSFT, so the trade would be asked about. When the
assistant records with the ledger's own table, a name the table does not
find is first handed to the model with the list (``pick_asset``), and the
program checks what comes back.

When to ask (``should_pick``), all five at once:

- the table is the ledger's own (``AssetTable.from_ledger``);
- the asset's cell is not empty;
- the table does not find it;
- it is not money, and not a name the built-in coin table knows for a coin
  the ledger lacks (``AssetTable.is_shielded``);
- it cannot be written as a ledger code (``is_symbol``). A word that can
  ("TSLA", "GOOGLE") is already told plainly that the ledger lacks it.

What the model is handed: the cell as the draft holds it (``spoken_key``
of what extraction copied) and the list of the assets the table may trade,
code, name and kind; never money, never the rest of the passage. With more
than ``MOST_LISTED`` of them it is not asked at all.

What is taken (``AssetPick.picked``), all four at once:

1. the code is one of the list's, after ``spoken_key``;
2. the words the model picked out (``said``) are not empty and are a run of
   the cell, after ``spoken_key``;
3. what is left of the cell around ``said`` is made only of the words of
   ``FILLER_WORDS`` ("的", "股票", "公司" ...), or nothing: "以太坊经典"
   read as "以太坊" leaves "经典", which is more than a filler, so nothing
   is taken;
4. the reply has the agreed shape and was not cut off.

Anything else, the model's failure among it, is a miss with its reason
(``PickMiss``); the trade then goes on as if nothing had been asked.

Why: the user names shares by their Chinese names; the model chooses from
the ledger's list and the program checks the choice (decided on
2026-11-25; the check of the words left over was added the same day).

Names defined here: ``MOST_LISTED``, ``PICK_REPLY_TOKENS``,
``FILLER_WORDS``, ``PICK_TABLE``, ``PickMiss``, ``AssetPick``,
``picking_list``, ``should_pick``, ``only_filler`` and ``pick_asset``.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass

from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.coins import spoken_key
from ledger_hand.core.ledger_limits import is_symbol
from ledger_hand.extraction.prompts.asset_pick import (
    ASSET_PICK_PROMPT,
    AssetPickPrompt,
    ListedAsset,
    listing_text,
)
from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelParameters,
    ModelPort,
    ModelReply,
    ReplyRecord,
    Role,
)

# Five hundred lines of about twelve tokens are some 6000 tokens, under half
# of the 16384 the model reads by default, which leaves room for the prompt
# and the reply. Set on 2026-11-25; not measured.
MOST_LISTED = 500

# A reply is a code and a few words of the user's, some 20 to 40 tokens;
# 100 leaves room for a long name and cuts a reply that runs on.
PICK_REPLY_TOKENS = 100

# The words that may stand beside an asset's name and still mean the asset,
# in lookup form, each with why. Only add to this list, and sparingly.
FILLER_WORDS: tuple[tuple[str, str], ...] = (
    ("的", "the joining word in 微软的股票"),
    ("股票", "微软股票, 苹果的股票: the company's shares"),
    ("股份", "英特尔股份: still the company's shares"),
    ("股", "这只股, 2股微软: the counter copied with the name"),
    ("公司", "苹果公司, 百事公司: the company itself"),
    ("集团", "阿里巴巴集团 and the like: the company itself"),
    ("这只", "这只英伟达: this one"),
    ("那只", "那只英伟达: that one"),
    ("STOCK", "Apple stock, written in capitals for lookup"),
    ("STOCKS", "Apple stocks"),
    ("SHARE", "an NVIDIA share"),
    ("SHARES", "NVIDIA shares"),
)

_SAID = "said"
_CODE = "code"
PICK_TABLE = {
    "type": "object",
    "properties": {_SAID: {"type": "string"}, _CODE: {"type": "string"}},
    "required": [_SAID, _CODE],
    "additionalProperties": False,
}
# A reply far longer than any one choice is not parsed at all.
_MAX_REPLY_CHARACTERS = 2000


class PickMiss(enum.Enum):
    """Why nothing was taken from the list."""

    NONE_ON_LIST = "the model said the list does not hold it"
    CODE_NOT_ON_LIST = "the model gave a code that is not an asset of the list"
    SAID_NOT_IN_WORDS = "the words the model picked out are not in what was said"
    WORDS_LEFT_OVER = "more was said than the asset's name"
    REPLY_UNREADABLE = "the model's reply was not the agreed shape"
    MODEL_FAILED = "the model could not be asked"
    LIST_TOO_LONG = "the ledger lists too many assets to hand the model"


@dataclass(frozen=True)
class AssetPick:
    """What came of picking an asset for ``word``, the cell as the draft holds it.

    ``code`` is the asset taken, and ``None`` when nothing was; then
    ``miss`` says why. ``said`` and ``answered`` are what the model gave,
    when its reply could be read. ``calls`` are the calls made; ``prompt``
    names the version used.
    """

    word: str
    code: str | None
    miss: PickMiss | None
    prompt: str
    said: str | None = None
    answered: str | None = None
    calls: tuple[ReplyRecord, ...] = ()

    @property
    def picked(self) -> bool:
        """Whether an asset of the list was taken."""
        return self.code is not None


def picking_list(assets: AssetTable) -> tuple[ListedAsset, ...]:
    """The assets the table may trade, in its order: code, name and kind ("other" if unknown)."""
    return tuple(
        ListedAsset(coin.symbol, coin.name, assets.kind_of(coin.symbol) or "other")
        for coin in assets.coins.coins
    )


def should_pick(word: str | None, assets: AssetTable) -> bool:
    """Whether the asset cell ``word`` is handed to the model to pick from the list."""
    if not assets.from_ledger or word is None or not spoken_key(word):
        return False
    if assets.find(word) is not None:
        return False
    if assets.money(word).reading is not MoneyReading.NOT_MONEY or assets.is_shielded(word):
        return False
    return not is_symbol(spoken_key(word))


def only_filler(rest: str) -> bool:
    """Whether ``rest``, spaces aside, is made only of filler words; nothing at all counts.

    For example "的股票" and "公司" are; "经典", "ETF" and "和英特尔" are not.
    """
    text = "".join(spoken_key(rest).split())
    words = sorted({spoken_key(word) for word, _ in FILLER_WORDS}, key=len, reverse=True)
    reachable = [True] + [False] * len(text)
    for end in range(1, len(text) + 1):
        reachable[end] = any(
            end >= len(word) and reachable[end - len(word)] and text[end - len(word) : end] == word
            for word in words
        )
    return reachable[len(text)]


def pick_asset(
    word: str,
    assets: AssetTable,
    model: ModelPort,
    *,
    prompt: AssetPickPrompt = ASSET_PICK_PROMPT,
    parameters: ModelParameters | None = None,
) -> AssetPick:
    """The asset of ``assets`` the model picks for ``word``, as the program checks it.

    ``word`` is the asset cell as the draft holds it. The model is called
    once, and never when the list is longer than ``MOST_LISTED``.
    """
    key = spoken_key(word)
    listing = picking_list(assets)
    if len(listing) > MOST_LISTED:
        return AssetPick(word=key, code=None, miss=PickMiss.LIST_TOO_LONG, prompt=prompt.name)
    try:
        reply = model.chat(
            _messages(prompt, key, listing), reply_schema=PICK_TABLE, parameters=parameters
        )
    except ModelError:
        return AssetPick(word=key, code=None, miss=PickMiss.MODEL_FAILED, prompt=prompt.name)
    calls = (reply.record,)
    read = _read(reply)
    if read is None:
        return AssetPick(
            word=key, code=None, miss=PickMiss.REPLY_UNREADABLE, prompt=prompt.name, calls=calls
        )
    said, answered = read
    miss = _miss(key, said, answered, listing)
    code = None if miss is not None else spoken_key(answered)
    return AssetPick(
        word=key,
        code=code,
        miss=miss,
        prompt=prompt.name,
        said=said,
        answered=answered,
        calls=calls,
    )


def _messages(
    prompt: AssetPickPrompt, word: str, listing: tuple[ListedAsset, ...]
) -> tuple[Message, ...]:
    messages = [Message(Role.SYSTEM, prompt.instructions)]
    for example in prompt.examples:
        messages.append(Message(Role.USER, listing_text(example.words, example.listing)))
        reply = json.dumps({_SAID: example.said, _CODE: example.code}, ensure_ascii=False)
        messages.append(Message(Role.ASSISTANT, reply))
    messages.append(Message(Role.USER, listing_text(word, listing)))
    return tuple(messages)


def _read(reply: ModelReply) -> tuple[str, str] | None:
    """The words and the code in the reply, or ``None`` when it is not the agreed shape."""
    if reply.record.finish is FinishReason.LENGTH_LIMIT or len(reply.text) > _MAX_REPLY_CHARACTERS:
        return None
    try:
        parsed = json.loads(reply.text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != {_SAID, _CODE}:
        return None
    said, code = parsed[_SAID], parsed[_CODE]
    if not isinstance(said, str) or not isinstance(code, str):
        return None
    return said, code


def _miss(word: str, said: str, answered: str, listing: tuple[ListedAsset, ...]) -> PickMiss | None:
    """Why the reply is not taken, or ``None`` when every check holds."""
    code = spoken_key(answered)
    if not code:
        return PickMiss.NONE_ON_LIST
    if code not in {spoken_key(asset.code) for asset in listing}:
        return PickMiss.CODE_NOT_ON_LIST
    picked_out = spoken_key(said)
    if not picked_out or picked_out not in word:
        return PickMiss.SAID_NOT_IN_WORDS
    if not _leaves_only_filler(word, picked_out):
        return PickMiss.WORDS_LEFT_OVER
    return None


def _leaves_only_filler(word: str, picked_out: str) -> bool:
    """Whether, at some place ``picked_out`` stands in ``word``, all around it is filler."""
    start = word.find(picked_out)
    while start != -1:
        if only_filler(word[:start] + word[start + len(picked_out) :]):
            return True
        start = word.find(picked_out, start + 1)
    return False
