"""One follow-up question in words: the program's label, and a sentence the model writes.

``write_question`` takes the facts the program settled about one question
(``QuestionFacts``), a model port and the coin table, and gives back a
``WrittenQuestion``: the label, the sentence, who wrote it, and why the
program's own sentence was used when it was.

What is asked is the program's: the model only words it. The label, which
says which trade and which field the question is about ("Trade 1 of 2:
price"), is always written by the program and goes before the sentence, so a
sentence that goes astray cannot make the person answer about the wrong
thing. The model gets the facts and the persona prompt and answers with
``{"question": "..."}``; the reply is checked, and the program's own
sentence (``templates``) is used instead when:

- the model port raised (unreachable, timed out, any of its kinds);
- the reply is not that shape, or was cut off;
- the sentence is not one plain question: empty, more than one line, longer
  than ``MAX_SENTENCE_LENGTH`` characters, not ending in a question mark, or
  holding more than one;
- the sentence brings in something that is not among the facts: a run of
  digits, a word the coin table knows, or a piece of Chinese writing that
  the facts do not hold; and, when the caller names the words for money,
  a word for money the facts do not name (so that a question about a
  trade priced in USD never asks for USDT);
- with the ledger's own asset table, the sentence calls the asset by a
  word that does not fit it: "coin" for a share or for an asset not
  recognised yet, or "币" at all (``Fallback.WRONG_ASSET_WORD``).

With the ledger's own table (``QuestionFacts.asset`` set), the label and
the facts name the asset cells "asset" and "fee asset", the reasons are
given in the ledger's table's words (``core.asset_words``), and the facts
say what the asset traded is called. With the built-in table nothing here
changes.

The model is asked once; it is never asked again for the same question.

Names defined here: ``write_question``, ``QuestionFacts``,
``WrittenQuestion``, ``Writer``, ``Fallback``, ``facts_text``, ``label_of``,
``QUESTION_TABLE`` and ``MAX_SENTENCE_LENGTH``.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass

from ledger_hand.asking.prompts.bookkeeper import BOOKKEEPER_PROMPT, BookkeeperPrompt
from ledger_hand.asking.templates import template_sentence
from ledger_hand.core.asset_words import AssetWord, cell_name, problem_words
from ledger_hand.core.coins import CoinTable
from ledger_hand.core.followup import AskCell, AskWhichCell, ConfirmCoin
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

# Long enough for any plain question about one field, short enough to read at a glance.
MAX_SENTENCE_LENGTH = 240
# A reply far longer than any one question is not parsed at all.
_MAX_REPLY_CHARACTERS = 10_000

_QUESTION_KEY = "question"
QUESTION_TABLE = {
    "type": "object",
    "properties": {_QUESTION_KEY: {"type": "string"}},
    "required": [_QUESTION_KEY],
    "additionalProperties": False,
}
_DIGITS = re.compile(r"\d+")
_LETTERS_AND_DIGITS = re.compile(r"[A-Za-z0-9]+")
_CHINESE = re.compile(r"[㐀-鿿]+")
_COIN_WORD = re.compile(r"\bcoins?\b", re.IGNORECASE)
_COIN_HANZI = "币"
_QUESTION_MARKS = "?？"
_ARTICLE = {AssetWord.SHARE: "a", AssetWord.COIN: "a", AssetWord.ASSET: "an"}


class Writer(enum.Enum):
    """Who wrote the sentence."""

    MODEL = "the model"
    PROGRAM = "the program"


class Fallback(enum.Enum):
    """Why the program's own sentence was used."""

    MODEL_FAILED = "the model could not be asked"
    REPLY_UNREADABLE = "the model's reply was not the agreed shape"
    NOT_ONE_QUESTION = "the model did not write one plain question"
    ADDS_FACTS = "the model's sentence holds something that is not among the facts"
    WRONG_ASSET_WORD = "the model's sentence calls the asset by a word that does not fit it"


@dataclass(frozen=True)
class QuestionFacts:
    """What the question may draw on, as the program settled it.

    ``trade`` counts from 1, of ``trades``. ``known`` are the cells already
    filled, as (name, value) in words. ``quoted`` is the passage's own words
    about the field, when there are some. ``notes`` are the program's lines
    shown beside the question; ``choices`` the answers to choose from, when
    there are some. ``word`` is the coin word a confirmation is about.
    ``money`` is the code of the money the trade is priced in, given to the
    model and named in the program's sentence for a price or a total; empty
    when it is not known; ``None`` with the built-in asset table, whose
    sentences name USDT. ``asset`` is what the ledger's own table calls
    the trade's asset (a share, a coin, an asset); ``None`` with the
    built-in table.
    """

    trade: int
    trades: int
    asked: AskCell | ConfirmCoin | AskWhichCell
    known: tuple[tuple[str, str], ...] = ()
    quoted: str | None = None
    notes: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()
    word: str | None = None
    money: str | None = None
    asset: AssetWord | None = None


@dataclass(frozen=True)
class WrittenQuestion:
    """The label, the sentence, who wrote it, why not the model when not, and the calls."""

    label: str
    sentence: str
    writer: Writer
    fallback: Fallback | None
    calls: tuple[ReplyRecord, ...]

    @property
    def text(self) -> str:
        """The label and the sentence together, as shown."""
        return f"{self.label} {self.sentence}"


def label_of(facts: QuestionFacts) -> str:
    """Which trade and which field the question is about, in the program's words."""
    asked = facts.asked
    if isinstance(asked, AskWhichCell):
        about = " or ".join(cell.value for cell in asked.cells)
    elif isinstance(asked, ConfirmCoin):
        about = f"is {facts.word!r} a coin?"
    else:
        about = cell_name(asked.cell, ledger=facts.asset is not None)
    return f"[Trade {facts.trade} of {facts.trades}: {about}]"


def facts_text(facts: QuestionFacts) -> str:
    """The facts as the model is given them, one per line."""
    asked = facts.asked
    ledger = facts.asset is not None
    lines = [f"Trade: {facts.trade} of {facts.trades}"]
    if isinstance(asked, AskWhichCell):
        named = ", ".join(cell_name(cell, ledger=ledger) for cell in asked.cells)
        lines.append(f"Ask: which one of {named} is wrong")
    elif isinstance(asked, ConfirmCoin):
        lines.append(f"Ask: whether {facts.word!r} is the symbol of a coin")
    else:
        lines.append(f"Ask for: the {cell_name(asked.cell, ledger=ledger)}")
    lines.append(f"Why: {problem_words(asked.because, ledger=ledger)}")
    if facts.asset is not None:
        lines.append(f"The asset traded is called: {_ARTICLE[facts.asset]} {facts.asset.value}")
    if facts.known:
        lines.append("Known: " + "; ".join(f"{name}: {value}" for name, value in facts.known))
    if facts.money:
        lines.append(f"Priced in: {facts.money}")
    if facts.quoted is not None:
        lines.append(f"The passage says: {facts.quoted!r}")
    lines.extend(f"Note: {note}" for note in facts.notes)
    lines.extend(f"Choice: {choice}" for choice in facts.choices)
    return "\n".join(lines)


def write_question(
    facts: QuestionFacts,
    model: ModelPort,
    coins: CoinTable,
    *,
    prompt: BookkeeperPrompt = BOOKKEEPER_PROMPT,
    parameters: ModelParameters | None = None,
    money_words: frozenset[str] = frozenset(),
) -> WrittenQuestion:
    """The question for ``facts``: the model's sentence when it will do, else the program's.

    ``money_words`` are the words for money, in lookup form, that the
    model's sentence may not bring in when the facts do not hold them; the
    built-in asset table hands in none.
    """
    label = label_of(facts)
    given = facts_text(facts)
    messages = (Message(Role.SYSTEM, prompt.instructions), Message(Role.USER, given))
    try:
        reply = model.chat(messages, reply_schema=QUESTION_TABLE, parameters=parameters)
    except ModelError:
        return _program_s(facts, label, Fallback.MODEL_FAILED, ())
    sentence = _sentence(reply)
    calls = (reply.record,)
    if sentence is None:
        return _program_s(facts, label, Fallback.REPLY_UNREADABLE, calls)
    if not _is_one_question(sentence):
        return _program_s(facts, label, Fallback.NOT_ONE_QUESTION, calls)
    if _adds_facts(sentence, given, coins) or _adds_money(sentence, given, money_words):
        return _program_s(facts, label, Fallback.ADDS_FACTS, calls)
    if _wrong_asset_word(sentence, facts.asset):
        return _program_s(facts, label, Fallback.WRONG_ASSET_WORD, calls)
    return WrittenQuestion(label, sentence, Writer.MODEL, None, calls)


def _program_s(
    facts: QuestionFacts, label: str, why: Fallback, calls: tuple[ReplyRecord, ...]
) -> WrittenQuestion:
    sentence = template_sentence(facts.asked, facts.word, facts.money, facts.asset)
    return WrittenQuestion(label, sentence, Writer.PROGRAM, why, calls)


def _sentence(reply: ModelReply) -> str | None:
    """The sentence in the reply, stripped, or ``None`` when the reply is not the shape."""
    if reply.record.finish is FinishReason.LENGTH_LIMIT or len(reply.text) > _MAX_REPLY_CHARACTERS:
        return None
    try:
        parsed = json.loads(reply.text)
    except (ValueError, RecursionError):
        return None
    sentence = parsed.get(_QUESTION_KEY) if isinstance(parsed, dict) else None
    return sentence.strip() if isinstance(sentence, str) else None


def _is_one_question(sentence: str) -> bool:
    marks = sum(sentence.count(mark) for mark in _QUESTION_MARKS)
    return (
        bool(sentence)
        and "\n" not in sentence
        and "\r" not in sentence
        and len(sentence) <= MAX_SENTENCE_LENGTH
        and sentence[-1] in _QUESTION_MARKS
        and marks == 1
    )


def _adds_facts(sentence: str, given: str, coins: CoinTable) -> bool:
    """Whether the sentence holds digits, a coin or Chinese writing the facts do not hold."""
    folded = given.casefold()
    if any(run not in given for run in _DIGITS.findall(sentence)):
        return True
    if any(run not in given for run in _CHINESE.findall(sentence)):
        return True
    for word in _LETTERS_AND_DIGITS.findall(sentence):
        coin = coins.find(word)
        if coin is not None and word.casefold() not in folded and coin.symbol not in given:
            return True
    return False


def _adds_money(sentence: str, given: str, money_words: frozenset[str]) -> bool:
    """Whether the sentence names, as a whole word, money the facts do not name."""
    if not money_words:
        return False
    named = {word.upper() for word in _LETTERS_AND_DIGITS.findall(given)}
    return any(
        word.upper() in money_words and word.upper() not in named
        for word in _LETTERS_AND_DIGITS.findall(sentence)
    )


def _wrong_asset_word(sentence: str, asset: AssetWord | None) -> bool:
    """Whether, with the ledger's table, the sentence says "币", or "coin" of a non-coin."""
    if asset is None:
        return False
    if _COIN_HANZI in sentence:
        return True
    return asset is not AssetWord.COIN and _COIN_WORD.search(sentence) is not None
