"""Reading the user's answer to a follow-up question: the rules first, the model only to copy.

``read_answer`` takes the answer as typed, what was asked (a follow-up of
``core.followup``), a model port and what the reading needs to know
(``AnswerSetting``), and gives back an ``AnswerReading`` whose outcome is one
of:

- ``Filled``: the value for a cell (``None`` to empty it), and the currency
  word written with a price, total or fee;
- ``Confirmed``: yes or no, to "is this word a coin's symbol";
- ``TwoTimes``: the time said is one the clocks showed twice that day, so
  the user is to choose;
- ``Commanded``: skip this trade, or drop the whole passage;
- ``NotRead``: why the answer could not be used, so the same question can be
  asked again with the reason.

The steps:

1. An empty answer is not read at all, and no model is asked.
2. The command words come first: skip this trade, or drop the whole passage
   (``answer_words``).
3. The whole answer is read by the rules: a number with ``read_number``, a
   time with ``read_time`` (the same current moment and zone as the
   passage), a coin with the coin table, and buy or sell, yes or no, "no
   fee", "the passage did not say it" and which of several cells with the
   word lists. A number, a time or a coin the rules understand but cannot
   take (a number they are unsure of, a time in the future) is not read
   further: the reason is handed back.
4. Only when the rules cannot read the whole answer is the model asked to
   copy, out of it, the one piece that gives what was asked
   (``prompts/answer.py``). The piece must be a piece of the answer, found
   the way a phrase is found in a passage (a number never cut in two), or
   it is not used. The piece is then read by the same rules as a whole
   answer. A reply that is not the shape is asked again as often as the
   caller allows; a failure of the model port is handed back as a reason.

A unit written with a number is the user's own writing and is used: on a
price or a total it names the pricing currency, on the fee the fee's
currency; on a quantity it must not name a currency other than the trade's
coin. A unit that names more than one currency is not used.

For the question about which of several cells is wrong, the answer has to
name exactly one of them with the words of ``answer_words``; the value after
the name is read as a number, or "the passage did not say it" empties the
cell. When the name is there and the value cannot be read, the model is
asked to copy the value for that cell.

``read_review_answer`` reads an answer once every trade is settled, by the
rules alone: done, drop the whole passage, or remove the trade of a given
number.

Nothing here reads the clock or the machine's zone, and nothing is written
anywhere.

Names defined here: ``read_answer``, ``read_review_answer``,
``AnswerReading``, ``AnswerSetting``, ``Filled``, ``Confirmed``,
``TwoTimes``, ``Commanded``, ``NotRead``, ``Outcome``, ``Command``,
``Confirmation``, ``AnswerProblem``, ``Review``, ``RemoveTrade``,
``CellValue`` and ``Asked``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ledger_hand.core.coins import CoinTable, means_usdt, spoken_key
from ledger_hand.core.followup import AskCell, AskWhichCell, Cell, ConfirmCoin
from ledger_hand.core.ledger_limits import QUOTE_CURRENCY, is_symbol
from ledger_hand.core.numbers import Doubt, Recognised, Unsure, read_number
from ledger_hand.core.timeparse import (
    Refusal,
    TimeRecognised,
    TwoCandidates,
    read_time,
)
from ledger_hand.core.trade import OccurredTime, Side
from ledger_hand.extraction.answer_table import (
    ANSWER_TABLE,
    AnswerPromptVersion,
    CopyProblem,
    CopyReplyUnreadable,
    Wanted,
    read_copy_reply,
)
from ledger_hand.extraction.answer_words import (
    CANCEL_WORDS,
    CELL_WORDS,
    CONNECTING_WORDS,
    DONE_WORDS,
    FIRST_WORDS,
    NO_FEE_WORDS,
    NO_WORDS,
    NOT_SAID_WORDS,
    NOTHING_WORDS,
    REMOVE_WORDS,
    SECOND_WORDS,
    SIDE_WORDS,
    SKIP_WORDS,
    YES_WORDS,
    tidy,
)
from ledger_hand.extraction.extractor import DEFAULT_ASKS_AGAIN, MAX_ASKS_AGAIN
from ledger_hand.extraction.passage import Passage, Piece, PieceMiss
from ledger_hand.extraction.prompting import PROBLEM_MARK
from ledger_hand.extraction.prompts.answer import ANSWER_PROMPT
from ledger_hand.extraction.unit_currency import currencies_in_unit, word_identity
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelPort,
    ReplyRecord,
    Role,
)

type CellValue = Side | str | Decimal | OccurredTime | None
type Asked = AskCell | ConfirmCoin | AskWhichCell

# The most trades a "remove N" may name; far more than one passage holds.
_MOST_TRADES = 1000


class Command(enum.Enum):
    """A command said in place of an answer."""

    SKIP = "leave this trade out"
    CANCEL = "drop the whole passage"


class Confirmation(enum.Enum):
    """Yes or no."""

    YES = "yes"
    NO = "no"


class AnswerProblem(enum.Enum):
    """Why an answer could not be used."""

    NO_ANSWER = "no answer was received"
    NOT_UNDERSTOOD = "the answer could not be read as what was asked"
    NOT_IN_ANSWER = "the model picked out words that are not in the answer"
    NUMBER_UNSURE = "the number cannot be pinned to one value"
    UNIT_NOT_THE_COIN = "the quantity names a coin other than the trade's"
    UNIT_NAMES_SEVERAL = "the unit names more than one currency"
    TIME_REFUSED = "the time cannot be taken"
    NO_CELL_NAMED = "the answer does not name exactly one of the values asked about"
    MODEL_FAILED = "the model could not be asked to read the answer"
    MODEL_REPLY_UNREADABLE = "the model's reply about the answer could not be read"


@dataclass(frozen=True)
class Filled:
    """The value for ``cell``; ``None`` empties it. ``unit`` is a currency word said with it."""

    cell: Cell
    value: CellValue
    unit: str | None = None


@dataclass(frozen=True)
class Confirmed:
    """Yes or no."""

    confirmation: Confirmation


@dataclass(frozen=True)
class TwoTimes:
    """The time said is one the clocks showed twice that day: both moments, the earlier first."""

    earlier: OccurredTime
    later: OccurredTime


@dataclass(frozen=True)
class Commanded:
    """A command said in place of an answer."""

    command: Command


@dataclass(frozen=True)
class NotRead:
    """Why the answer could not be used; ``cause`` is the core's or the model port's reason."""

    problem: AnswerProblem
    cause: Doubt | Refusal | ModelErrorKind | CopyProblem | None = None


Outcome = Filled | Confirmed | TwoTimes | Commanded | NotRead


@dataclass(frozen=True)
class AnswerReading:
    """The outcome, what the model copied (when it was asked), and a record of each call."""

    outcome: Outcome
    copied: str | None
    calls: tuple[ReplyRecord, ...]


@dataclass(frozen=True)
class AnswerSetting:
    """What reading an answer needs to know.

    ``now`` and ``zone`` are those of the passage. ``coin`` and ``fee_coin``
    are the trade's coin and fee coin as the draft holds them; a number may
    carry them as its unit. ``candidates`` are two moments the user is to
    choose from, when the time is asked with them.
    """

    now: datetime
    zone: str
    coins: CoinTable
    coin: str | None = None
    fee_coin: str | None = None
    candidates: tuple[OccurredTime, ...] = ()

    @property
    def coin_words(self) -> tuple[str, ...]:
        return tuple(word for word in (self.coin, self.fee_coin) if word is not None)


type _Read = Callable[[str], Outcome | None]
type _Find = Callable[[Passage, str], Piece | PieceMiss]


@dataclass(frozen=True)
class _Reader:
    """How one kind of answer is read.

    ``wanted`` is what the model is asked to copy (``None``: the rules always
    read it), ``read`` the rule, and ``find`` how a copied piece is found in
    the answer.
    """

    wanted: Wanted | None
    read: _Read
    find: _Find


def _find_plain(passage: Passage, phrase: str) -> Piece | PieceMiss:
    return passage.find(phrase)


def read_answer(
    answer: str,
    asked: Asked,
    model: ModelPort,
    setting: AnswerSetting,
    *,
    prompt: AnswerPromptVersion = ANSWER_PROMPT,
    parameters: ModelParameters | None = None,
    asks_again: int = DEFAULT_ASKS_AGAIN,
) -> AnswerReading:
    """What ``answer`` says about what was ``asked``, or why it cannot be used."""
    if not 0 <= asks_again <= MAX_ASKS_AGAIN:
        raise ValueError(f"asks_again must be from 0 to {MAX_ASKS_AGAIN}")
    tidied = tidy(answer)
    if not tidied:
        return AnswerReading(NotRead(AnswerProblem.NO_ANSWER), None, ())
    command = _command(tidied)
    if command is not None:
        return AnswerReading(Commanded(command), None, ())
    reader = _which_cell(answer, asked, setting) if isinstance(asked, AskWhichCell) else None
    if isinstance(reader, Filled | NotRead):
        return AnswerReading(reader, None, ())
    if reader is None:
        reader = _reader(asked, setting)
        by_rule = reader.read(answer)
        if by_rule is not None:
            return AnswerReading(by_rule, None, ())
    if reader.wanted is None:
        return AnswerReading(NotRead(AnswerProblem.NOT_UNDERSTOOD), None, ())
    return _copied_by_model(answer, reader, reader.wanted, model, (prompt, parameters, asks_again))


def _command(tidied: str) -> Command | None:
    if tidied in SKIP_WORDS:
        return Command.SKIP
    if tidied in CANCEL_WORDS:
        return Command.CANCEL
    return None


# --- one reader for each kind of question -----------------------------------

_AMOUNT_WANTED = {
    Cell.QUANTITY: Wanted.QUANTITY,
    Cell.PRICE: Wanted.PRICE,
    Cell.TOTAL: Wanted.TOTAL,
    Cell.FEE: Wanted.FEE,
}


def _reader(asked: AskCell | ConfirmCoin, setting: AnswerSetting) -> _Reader:
    if isinstance(asked, ConfirmCoin):
        return _Reader(Wanted.YES_OR_NO, _read_confirmation, _find_plain)
    cell = asked.cell
    if cell in _AMOUNT_WANTED:
        return _amount_reader(cell, setting)
    if cell is Cell.SIDE:
        return _Reader(Wanted.SIDE, _read_side, _find_plain)
    if cell in (Cell.COIN, Cell.FEE_COIN):
        wanted = Wanted.COIN if cell is Cell.COIN else Wanted.FEE_COIN
        return _Reader(wanted, lambda text: _read_coin(text, cell, setting), _find_plain)
    if cell is Cell.OCCURRED:
        return _Reader(Wanted.TIME, lambda text: _read_time(text, setting), _find_plain)
    return _Reader(None, lambda text: _read_text(text, cell), _find_plain)


def _amount_reader(cell: Cell, setting: AnswerSetting) -> _Reader:
    units = setting.coin_words
    return _Reader(
        _AMOUNT_WANTED[cell],
        lambda text: _read_amount(text, cell, setting),
        lambda passage, phrase: passage.find_number(phrase, units),
    )


def _read_side(text: str) -> Outcome | None:
    side = SIDE_WORDS.get(tidy(text))
    return None if side is None else Filled(Cell.SIDE, side)


def _read_confirmation(text: str) -> Outcome | None:
    tidied = tidy(text)
    if tidied in YES_WORDS:
        return Confirmed(Confirmation.YES)
    if tidied in NO_WORDS:
        return Confirmed(Confirmation.NO)
    return None


def _read_coin(text: str, cell: Cell, setting: AnswerSetting) -> Outcome | None:
    known = setting.coins.find(text)
    if known is not None:
        return Filled(cell, known.symbol)
    if means_usdt(text):
        return Filled(cell, QUOTE_CURRENCY)
    key = spoken_key(text)
    return Filled(cell, key) if is_symbol(key) else None


def _read_text(text: str, cell: Cell) -> Outcome:
    if tidy(text) in NOTHING_WORDS:
        return Filled(cell, None)
    return Filled(cell, text.strip())


def _read_amount(text: str, cell: Cell, setting: AnswerSetting) -> Outcome | None:
    if cell is Cell.FEE and tidy(text) in NO_FEE_WORDS:
        return Filled(Cell.FEE, Decimal(0))
    reading = read_number(text, extra_units=setting.coin_words)
    if isinstance(reading, Unsure):
        return NotRead(AnswerProblem.NUMBER_UNSURE, reading.reason)
    if not isinstance(reading, Recognised):
        return None
    if reading.unit is None:
        return Filled(cell, reading.value)
    named = currencies_in_unit(reading.unit, setting.coins, setting.coin_words)
    if cell is Cell.QUANTITY:
        coin = None if setting.coin is None else word_identity(setting.coin, setting.coins)
        if any(word.identity != coin for word in named):
            return NotRead(AnswerProblem.UNIT_NOT_THE_COIN)
        return Filled(cell, reading.value)
    if len(named) > 1:
        return NotRead(AnswerProblem.UNIT_NAMES_SEVERAL)
    return Filled(cell, reading.value, named[0].text if named else None)


def _read_time(text: str, setting: AnswerSetting) -> Outcome | None:
    if len(setting.candidates) == 2:
        chosen = tidy(text)
        if chosen in FIRST_WORDS:
            return Filled(Cell.OCCURRED, setting.candidates[0])
        if chosen in SECOND_WORDS:
            return Filled(Cell.OCCURRED, setting.candidates[1])
    reading = read_time(text, setting.now, setting.zone)
    if isinstance(reading, TimeRecognised):
        return Filled(Cell.OCCURRED, reading.time)
    if isinstance(reading, TwoCandidates):
        return TwoTimes(reading.earlier, reading.later)
    if reading.reason is Refusal.UNKNOWN_WORDING:
        return None
    return NotRead(AnswerProblem.TIME_REFUSED, reading.reason)


# --- which of several cells is wrong ----------------------------------------


def _which_cell(answer: str, asked: AskWhichCell, setting: AnswerSetting) -> Outcome | _Reader:
    tidied = tidy(answer)
    named = _named_cell(tidied, asked.cells)
    if named is None:
        return NotRead(AnswerProblem.NO_CELL_NAMED)
    cell, rest = named
    if any(words in tidied for words in NOT_SAID_WORDS):
        return Filled(cell, None)
    by_rule = _read_amount(_value_part(rest), cell, setting)
    return by_rule if by_rule is not None else _amount_reader(cell, setting)


def _named_cell(tidied: str, cells: tuple[Cell, ...]) -> tuple[Cell, str] | None:
    """The one cell of ``cells`` the answer names, and what follows its name; else ``None``.

    The answer is read from the left, taking the longest name at each place,
    so that "总价" counts as the total and not also as the price.
    """
    names = sorted(
        ((word, cell) for cell, words in CELL_WORDS.items() for word in words),
        key=lambda pair: -len(pair[0]),
    )
    found: list[tuple[Cell, int]] = []
    place = 0
    while place < len(tidied):
        match = next(((w, c) for w, c in names if tidied.startswith(w, place)), None)
        if match is None:
            place += 1
            continue
        found.append((match[1], place + len(match[0])))
        place += len(match[0])
    asked = [(cell, end) for cell, end in found if cell in cells]
    if len({cell for cell, _ in asked}) != 1:
        return None
    cell, end = asked[0]
    return cell, tidied[end:]


def _value_part(rest: str) -> str:
    """What follows a cell's name, without the word that joins the two ("is", "是")."""
    text = rest.strip().lstrip(",:=").strip()
    for word in sorted(CONNECTING_WORDS, key=len, reverse=True):
        if text.startswith(word):
            return text[len(word) :].strip()
    return text


# --- asking the model to copy the piece -------------------------------------


def _copied_by_model(
    answer: str,
    reader: _Reader,
    wanted: Wanted,
    model: ModelPort,
    how: tuple[AnswerPromptVersion, ModelParameters | None, int],
) -> AnswerReading:
    prompt, parameters, asks_again = how
    calls: list[ReplyRecord] = []
    problems: list[CopyProblem] = []
    for _ in range(asks_again + 1):
        last = problems[-1] if problems else None
        messages = _messages(prompt, wanted, answer, last)
        try:
            reply = model.chat(messages, reply_schema=ANSWER_TABLE, parameters=parameters)
        except ModelError as error:
            failed = NotRead(AnswerProblem.MODEL_FAILED, error.kind)
            return AnswerReading(failed, None, tuple(calls))
        calls.append(reply.record)
        phrase = read_copy_reply(reply)
        if not isinstance(phrase, CopyReplyUnreadable):
            return AnswerReading(_from_phrase(phrase, answer, reader), phrase, tuple(calls))
        problems.append(phrase.problem)
    unreadable = NotRead(AnswerProblem.MODEL_REPLY_UNREADABLE, problems[-1])
    return AnswerReading(unreadable, None, tuple(calls))


def _messages(
    prompt: AnswerPromptVersion, wanted: Wanted, answer: str, problem: CopyProblem | None
) -> tuple[Message, ...]:
    asked = f"Field: {prompt.fields[wanted]}\n\nAnswer:\n{answer}"
    messages = [Message(Role.SYSTEM, prompt.instructions), Message(Role.USER, asked)]
    if problem is not None:
        messages.append(Message(Role.USER, prompt.ask_again.replace(PROBLEM_MARK, problem.value)))
    return tuple(messages)


def _from_phrase(phrase: str, answer: str, reader: _Reader) -> Outcome:
    if not phrase.strip():
        return NotRead(AnswerProblem.NOT_UNDERSTOOD)
    found = reader.find(Passage(answer), phrase)
    if isinstance(found, PieceMiss):
        return NotRead(AnswerProblem.NOT_IN_ANSWER)
    by_rule = reader.read(found.text)
    return by_rule if by_rule is not None else NotRead(AnswerProblem.NOT_UNDERSTOOD)


# --- once every trade is settled --------------------------------------------


class Review(enum.Enum):
    """What may be said once every trade is settled, besides removing one."""

    DONE = "done: keep the records as they are"
    CANCEL = "drop the whole passage"


@dataclass(frozen=True)
class RemoveTrade:
    """Remove the trade shown with ``number``, counting from 1; it counts as skipped."""

    number: int


def read_review_answer(answer: str) -> Review | RemoveTrade | NotRead:
    """What an answer says once every trade is settled, read by the rules alone."""
    tidied = tidy(answer)
    if not tidied:
        return NotRead(AnswerProblem.NO_ANSWER)
    if tidied in DONE_WORDS:
        return Review.DONE
    if tidied in CANCEL_WORDS:
        return Review.CANCEL
    number = _removed(tidied)
    return RemoveTrade(number) if number is not None else NotRead(AnswerProblem.NOT_UNDERSTOOD)


def _removed(tidied: str) -> int | None:
    """The trade's number in "remove 2" or "去掉第 2 笔", or ``None``."""
    word = next((word for word in REMOVE_WORDS if tidied.startswith(word)), None)
    if word is None:
        return None
    rest = tidied[len(word) :].strip()
    for prefix in ("trade", "#", "第"):
        rest = rest.removeprefix(prefix).strip()
    reading = read_number(rest.removesuffix("笔").strip())
    if not isinstance(reading, Recognised) or reading.unit is not None:
        return None
    value = reading.value
    if value != value.to_integral_value() or not 1 <= value <= _MOST_TRADES:
        return None
    return int(value)
