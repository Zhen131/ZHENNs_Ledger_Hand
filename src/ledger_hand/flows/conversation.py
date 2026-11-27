"""One thing the user says to the assistant, with recording a trade handed to the program.

``say`` is the entry for each thing the user says. It is handed the chat as
it stands (``AssistantChat``: the assistant's ``Chat``, and a passage whose
question waits for its answer, or a change that waits for the user to say
which trade or which amount follows, if one does) and gives back what came
of it (``Said``), with the chat to hand the next time. It takes one of these
routes (``Route``):

- A question waits: what the user says is its answer. The model that
  chooses tools is not asked; the recording flow reads the answer
  (``recording.answer``), "skip" and "cancel" among them, and asks the same
  question again when the answer cannot be used. A change that waits is
  answered the same way, read by the program (``editing.answer``). Only one
  thing ever waits: a new question takes the place of the one answered.
- Otherwise, money moved that the assistant does not record, said and not
  asked (a deposit, a withdrawal, an exchange of moneys or a dividend,
  ``money_asks.statement``), naming no coin or share and saying no buy or
  sell, is answered by the program before the model is asked: it records
  none of them, so it says so and sends nothing (``Route.MANUAL``). Said
  beside a coin or share named, or a buy or a sell, the trade goes on as
  below, and the reply ends with a line saying that part is to be recorded
  in the ledger by hand, and another when no trade was recorded either:
  never half of it done unsaid. (Decided on 2026-11-26.)
- Otherwise, a question about cash is caught before the model is asked
  (``cash_question.caught``), read in the words tidied, as the model
  would read them; a deposit or a withdrawal it catches is passed over
  when a buy or a sell was spoken of beside one, as above. When it catches
  none, how much of any money is still had ("我还有多少欧元") is caught by
  ``money_asks.left_asked``. Then the program asks the ledger for its cash
  balances once (``cash_answers``) and says its own fixed words, never the
  model's (``Route.CASH``); when the words were said, not asked, and name
  a coin or share ("今天现金买了2股KO"), the reply ends with a line that
  they were taken as a question about cash, and a trade meant is to be
  said again on its own (``TRADE_AS_CASH_WORDS``, 2026-11-26). With the
  balances, a table of every money's balance, as the ledger gave it,
  nothing added up or converted; a ledger with no tool for them (an
  older one) gets ``cash_question.CASH_WORDS``, as before. (Decided on
  2026-11-25; the balances, on 2026-11-26.)
- Otherwise the model chooses tools (``assisting.take_turn``). When it asks
  to record a trade, what the user said, word for word, is handed to the
  recording flow (``recording.start``), once, however many such calls it
  made; the flow judges it, extracts the trades and asks what is missing.
  The model is not asked again in this turn: the program tells the user
  the question, or that a proposal was sent, or why nothing was.
- When the model goes wrong two steps in a row, the program takes over
  once: it hands what the user said to the recording flow as what may be
  a trade, and says what the flow found, in the same words as when the
  model asks to record: only things the ledger does not record, such as an
  open order, is said with its reason. Only when the flow finds no trade at
  all is the user told it could not be done. A turn stopped at the step
  limit, or by a failure, is not taken over. (Decided on 2026-11-24.)
  When the second wrong step holds a change or a deletion, what was said
  is not tried as a trade: the program goes on from that call alone
  (``editing.taken_over``), and when nothing in it can be gone on with,
  the turn's own words stand.

When the model answers in its own words having looked nothing up, and a
number the user never said in this chat stands in them beside a money
("50 USDT"), they are not shown: the
user is told ``cash_question.CASH_WORDS`` instead, or, when the ledger has
a tool for cash balances, ``cash_answers.WITHHELD_WORDS``, and the turn
says why (``TurnResult.withheld``); the chat keeps the program's words.
Whether the ledger has that tool is asked when it matters this time (for
those words, a question about cash, or a table of holdings or of sums
laid out) and kept in ``Said.cash_seen``, so that the page never asks the
ledger while it draws.

When the model asks to change or delete a trade, the program goes on with
that call (``editing.start``) and says how it ended; the model is not
asked again in this turn. What reached the ledger is kept apart from a
recording's (``Said.edit_sent``), and its proposal joins the chat's.

Once every trade is settled, the records are sent to the ledger as one
proposal (``proposing``); nothing is confirmed here, since the user confirms
on the ledger's own page. The program's words come from ``record_words``;
none of them is written by the model, and no figure of a trade passes
through it, apart from the number of a quantity said in another unit,
said back as it was read.

The recording flow records with the asset table made from the ledger's own
list of assets (``ledger_table``), asked for once when recording begins:
only an asset of the ledger can be recorded, priced in money the ledger
prices trades in. A trade whose quantity was said in a unit that is not
the asset traded ("25U" of ETH) is held back at the start, asked nothing
about and not sent; the reply says why (``recording.held_other_unit``).
The name of an asset the table does not find, and that cannot be written
as a code ("微软"), can be handed to the model to pick from the ledger's
list (``recording.start``, ``pick_assets``); an asset taken is said in the
reply that begins the recording and in the one that ends it, with that the
model matched it (``record_words``). It is off (``ASSISTANT_PICKS_ASSETS``):
measured, it picked listed assets for names the ledger lacks. Such a name
is asked about, and the question says to add the asset first.
Before that, the program matches such a name itself, with no call to the
model (``recording.start``, ``name_table`` and ``remembered``;
``core.stock_names``): first by the user's earlier answers kept in the
names file handed in (``names``, ``asset_names``), then by its own table
of common company names (``name_table``, on unless the caller says off).
A name matched is said in the same replies, with where it was taken
from. When the user answers the question "which asset" of a trade whose
cell held a name with a code of the ledger, that name and code are kept
in the names file (``stock_names.worth_remembering``), for the kind of
ledger the file was handed in for; with no names file, nothing is read
or kept.
A vague word for money ("美金", "刀", "$") that the trade itself does not
settle is guessed from the asset's last trade in the ledger: the flow is
handed the one function that asks (``last_money.last_money_of``), each
time it is started or answered, and the reply says each money guessed
(``record_words``). (The product owner's rule of 2026-11-25.)
The recording flow is handed no book of its own: what the assistant
records goes to the ledger. So there is no reminder that the same words
were saved before, and a coin the user confirms is known for that passage
only. Its calls to the model are not counted against the step limit; the
flow's progress keeps them apart.

Whatever is said, typed or as an answer, is first tidied
(``spoken_text.tidy_spoken``, in the zone handed in): number words and a
time said in Chinese are written in digits, without changing what they
are. From then on the words tidied are what was said: the model sees
them, the flow reads them, and the chat keeps them. The words as they
were said go to the ledger as each trade's own record of them
(``Progress.raw_text``), and with each change or deletion asked for
(``editing``, ``raw_text``); ``Said.read_as`` holds both, with each change.
(Decided on 2026-11-25: the program tidies, so the model never reads a
number or a time it might change.)

Words typed or said are extracted with the version of the prompt their
language calls for (``prompt_language.extract_prompt_for``): words with a
Chinese character in them, once tidied, with
``ASSISTANT_CHINESE_EXTRACT_PROMPT``, or the version handed to ``say`` for
Chinese (``extract_for_chinese``, which the measures use); words with none
with ``first-3``. A screenshot is always extracted with ``first-3``
(``ASSISTANT_EXTRACT_PROMPT``): no other version was measured on one.

A screenshot read is said through ``say_from_reading``: the text read, as
the person left it, and the note typed beside it are joined into one
passage (``screenshot.start_from_reading``) and recorded exactly as the
words typed are, with the same asset table, the same prompt versions and
the same holding back, set in one place (``_start``); the model that
chooses tools is not asked, and no book is handed in. It goes into the
chat as what the user said, and the program's reply as the assistant's
(``Route.SCREENSHOT``). It is for when nothing waits for an answer.

``Said.words_by`` says who wrote the words the user is told (``WordsBy``):
the model, the program's own fixed words, or the recording's question, so
that a caller shows it as it is rather than work it out.

This module reads no clock, no zone and no settings: all are handed in.

Names defined here: ``Route``, ``WordsBy``, ``AssistantChat``, ``Said``,
``ScreenshotText``, ``say``, ``say_from_reading``,
``ASSISTANT_SCREEN_PROMPT``, ``ASSISTANT_EXTRACT_PROMPT``,
``ASSISTANT_CHINESE_EXTRACT_PROMPT``, ``ASSISTANT_PICK_PROMPT``,
``ASSISTANT_PICKS_ASSETS`` and ``ASSISTANT_NAME_TABLE``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from ledger_hand.assistant.edit_calls import EDIT_TOOLS
from ledger_hand.assistant.edit_words import not_done_words
from ledger_hand.assistant.outcome import Chat, Ending, TakenCall, TurnResult
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.assets import AssetTable
from ledger_hand.core.cash_words import CashAsk, held_names
from ledger_hand.core.followup import AskCell, Cell
from ledger_hand.core.ledger_records import Asset
from ledger_hand.core.ledger_table import names_of, table_of
from ledger_hand.core.money_asks import (
    Statement,
    asks_or_requests,
    left_asked,
    may_be_exchange,
    named_money,
    names_a_holding,
    statement,
)
from ledger_hand.core.spoken_text import Tidied, tidy_spoken
from ledger_hand.core.stock_names import worth_remembering
from ledger_hand.extraction.picture_reading import PictureRead
from ledger_hand.extraction.prompt_language import extract_prompt_for
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.asset_pick import ASSET_PICK_PROMPT
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.flows import editing, recording
from ledger_hand.flows.asset_names import NamesFile, read_names, remember
from ledger_hand.flows.assisting import close_editing, close_recording, first_edit, take_turn
from ledger_hand.flows.cash_answers import (
    NOT_RECORDED_EITHER,
    TRADE_AS_CASH_WORDS,
    WITHHELD_WORDS,
    CashSeen,
    cash_words,
    look_up,
    manual_tail,
    manual_words,
    money_of_the_ledger,
)
from ledger_hand.flows.cash_question import CASH_WORDS, caught, withheld_cash
from ledger_hand.flows.editing import Edited, EditEnding, EditSent, EditWaiting
from ledger_hand.flows.last_money import last_money_of
from ledger_hand.flows.progress import DEFAULT_TUNING, Progress, Tuning
from ledger_hand.flows.proposing import propose
from ledger_hand.flows.record_words import reply_for
from ledger_hand.flows.recorded import (
    SETTLED_STAGES,
    STAGE_ENDINGS,
    Recorded,
    RecordEnding,
    Sent,
)
from ledger_hand.flows.screenshot import joined_passage, start_from_reading
from ledger_hand.ports import LedgerError, LedgerPort, Message, ModelPort, Role, ToolCall
from ledger_hand.settings import DEFAULT_PRICE_GAP_TIMES, DEFAULT_RATE_GAP_PERCENT

# The prompt versions the assistant judges and extracts what the user said
# with. The record page keeps the first ones. Measured on 2026-11-25 on
# sentences about a share bought with dollars, the first judging version
# read some as no trade at all, and the first extraction version put gaps
# into phrases; the assistant judges with the second judging version and
# extracts with the third extraction version, the one measured best.
ASSISTANT_SCREEN_PROMPT = SCREEN_PROMPT_2
ASSISTANT_EXTRACT_PROMPT = FIRST_PROMPT_3
# The version words with a Chinese character in them are extracted with.
ASSISTANT_CHINESE_EXTRACT_PROMPT = FIRST_PROMPT_3
# The prompt version that picks, from the ledger's list, the asset a name not
# found names. The three versions measured on the practice half of the names
# set tied, so the first is kept.
ASSISTANT_PICK_PROMPT = ASSET_PICK_PROMPT
# Whether the assistant hands such a name to the model at all: off. Measured
# on 2026-11-25, every version picked a listed asset for some name the
# ledger lacks ("谷歌" as AAPL, "柚子币" as SOL), so a wrong asset would be
# sent; the step stays in the code, off, until a way passes the names set.
ASSISTANT_PICKS_ASSETS = False
# Whether the assistant matches a name the ledger's table does not find by
# the program's own table of common company names, when the caller does not
# say (read each time ``say`` is called): on. Matching whole names only, it
# cannot match a name the ledger lacks to another asset (decided on 2026-11-27).
ASSISTANT_NAME_TABLE = True

# After a takeover, only this ending means it could not be done at all.
_NOT_A_TRADE = frozenset({RecordEnding.NO_TRADE})
# A turn of the model that ended with the user told something, nothing failing.
_TOLD = frozenset({Ending.ANSWERED, Ending.ANSWERED_BY_PROGRAM})
# The tables that hold money but never cash: the page says so under each.
_WITHOUT_CASH = frozenset({ToolName.GET_POSITIONS, ToolName.GET_PERIOD_SUMMARY})
# A question about money put in or taken out, passed over beside a buy or a sell.
_MOVED = frozenset({CashAsk.DEPOSIT, CashAsk.WITHDRAWAL})


class Route(enum.Enum):
    """Which way what the user said went."""

    MODEL = "the model chose the tools"
    ANSWER = "taken as the answer to the question waiting"
    TAKEOVER = "the program took over after two wrong steps"
    SCREENSHOT = "recorded from a screenshot read, the model that chooses tools not asked"
    CASH = "answered by the program itself: a question about cash, which it cannot look up"
    MANUAL = (
        "answered by the program itself: money moved that the assistant does not record, "
        "to be recorded in the ledger by hand"
    )


class WordsBy(enum.Enum):
    """Who wrote the words the user is told."""

    MODEL = "the model"
    PROGRAM = "the program's own words"
    QUESTION = "the recording's question"


@dataclass(frozen=True, kw_only=True)
class AssistantChat:
    """The chat so far, and what waits for the user's answer, if anything does.

    ``recording`` is a passage whose question waits; ``editing`` a change
    that waits for which trade, or which amount follows. At most one waits.
    """

    chat: Chat = Chat()
    recording: Progress | None = None
    editing: EditWaiting | None = None

    def __post_init__(self) -> None:
        if self.recording is not None and self.editing is not None:
            raise ValueError("only one thing waits for the user's answer at a time")


@dataclass(frozen=True, kw_only=True)
class Said:
    """What came of one thing the user said.

    ``turn`` is the model's turn, when the model was asked; ``recorded`` how
    recording ended, when there was any; ``edited`` how a change or a
    deletion ended, when there was one; ``cash`` which kind of question
    about cash was caught, when one was; ``cash_seen`` what the ledger said
    of its cash, when it was asked this time (its balances, or that it has
    no tool for them); ``manual`` the money moved said that the assistant
    does not record, when there was any; ``reply`` what the user is told;
    ``state`` the chat to hand the next time. ``read_as`` is what was said
    and the words tidied from it, for words typed or answered; ``None`` for
    a screenshot's text, which is not tidied.
    """

    route: Route
    reply: str
    state: AssistantChat
    turn: TurnResult | None = None
    recorded: Recorded | None = None
    edited: Edited | None = None
    read_as: Tidied | None = None
    cash: CashAsk | None = None
    cash_seen: CashSeen | None = None
    manual: Statement | None = None

    @property
    def edit_sent(self) -> EditSent | None:
        """The change or deletion that reached the ledger this time; ``None`` for none."""
        return self.edited.sent if self.edited is not None else None

    @property
    def sent(self) -> Sent | None:
        """What reached the ledger this time, by the program's own word; ``None`` for nothing."""
        return self.recorded.sent if self.recorded is not None else None

    @property
    def words_by(self) -> WordsBy:
        """Who wrote ``reply``: the model only when it answered and its words were shown.

        A question's own sentence may still be the model's; the question says
        (``Question.writer``).
        """
        if self.recorded is not None and self.recorded.question is not None:
            return WordsBy.QUESTION
        turn = self.turn
        if self.recorded is not None or self.edited is not None or turn is None:
            return WordsBy.PROGRAM
        if turn.ending is Ending.ANSWERED and turn.withheld is None:
            return WordsBy.MODEL
        return WordsBy.PROGRAM

    @property
    def well_ended(self) -> bool:
        """Whether it was done, or the user was told why not, with nothing failing."""
        if self.route in (Route.CASH, Route.MANUAL):
            return True
        if self.edited is not None:
            return self.edited.ending is not EditEnding.LEDGER_FAILED
        if self.recorded is not None:
            if self.route is Route.TAKEOVER and self.recorded.ending in _NOT_A_TRADE:
                return False
            return self.recorded.well_ended
        return self.turn is not None and self.turn.ending in _TOLD


@dataclass(frozen=True, kw_only=True)
class ScreenshotText:
    """A screenshot read, and the two texts to record from it: the text read, as the
    person left it, and the note typed beside it."""

    reading: PictureRead
    text: str
    note: str = ""


@dataclass(frozen=True)
class _Around:
    """What every part of one thing said is handed: the ports, the moment, the zone.

    ``raw_text`` is the words as the user said them, when tidying changed
    them; a trade recorded from them is sent with these words.
    ``chinese`` is the version words with Chinese in them are extracted with.
    ``gap`` is how many times apart a price and the market price are far;
    ``rate_gap`` how far apart, in a hundred, the rate of a trade paid in
    another money and the last such rate are. ``name_table`` says whether
    names are matched by the program's table of company names; ``names``
    is the file of the user's answers, or ``None`` to read and keep none.
    """

    model: ModelPort
    ledger: LedgerPort
    now: datetime
    zone: str
    tuning: Tuning
    raw_text: str | None = None
    chinese: PromptVersion = ASSISTANT_CHINESE_EXTRACT_PROMPT
    gap: Decimal = DEFAULT_PRICE_GAP_TIMES
    rate_gap: Decimal = DEFAULT_RATE_GAP_PERCENT
    name_table: bool = ASSISTANT_NAME_TABLE
    names: NamesFile | None = None


def say(
    state: AssistantChat,
    said: str,
    *,
    model: ModelPort,
    ledger: LedgerPort,
    now: datetime,
    zone: str,
    max_steps: int,
    tuning: Tuning = DEFAULT_TUNING,
    extract_for_chinese: PromptVersion | None = None,
    price_gap: Decimal = DEFAULT_PRICE_GAP_TIMES,
    rate_gap: Decimal = DEFAULT_RATE_GAP_PERCENT,
    name_table: bool | None = None,
    names: NamesFile | None = None,
) -> Said:
    """What comes of the user saying ``said`` after ``state``.

    ``tuning`` is how the recording flow calls the model to word a question;
    the caller takes it from the settings (``recording.tuning_from``).
    ``said`` is tidied first, and the words tidied go on in its place.
    ``extract_for_chinese``, when given, is the version words with Chinese
    in them are extracted with, in place of the assistant's own.
    ``price_gap`` is how many times apart a trade's price and the ledger's
    market price are far (``settings.load_price_gap_times``), and
    ``rate_gap`` how far apart, in a hundred, a rate between two moneys and
    the last one are (``settings.load_rate_gap_percent``).
    ``name_table`` says whether a name the ledger's table does not find is
    matched by the program's table of company names; left out, as
    ``ASSISTANT_NAME_TABLE`` says (on), read when called; and
    ``names`` is the file of the user's answers to read and keep, or
    ``None`` (the default) to read and keep none.
    """
    read_as = tidy_spoken(said, zone)
    chinese = extract_for_chinese or ASSISTANT_CHINESE_EXTRACT_PROMPT
    raw_text = said if read_as.changed else None
    around = _Around(
        model,
        ledger,
        now,
        zone,
        tuning,
        raw_text,
        chinese,
        price_gap,
        rate_gap,
        name_table=ASSISTANT_NAME_TABLE if name_table is None else name_table,
        names=names,
    )
    done = _said(state, read_as.text, around, max_steps)
    return replace(_cash_known(done, ledger), read_as=read_as)


def _cash_known(done: Said, ledger: LedgerPort) -> Said:
    """``done``, with whether the ledger has a tool for cash, when a table of holdings or of
    sums was laid out and it is not known yet; the page reads it and never asks."""
    if done.cash_seen is not None or done.turn is None:
        return done
    if not any(lookup.tool in _WITHOUT_CASH for lookup in done.turn.lookups):
        return done
    return replace(done, cash_seen=look_up(ledger))


def _said(state: AssistantChat, said: str, around: _Around, max_steps: int) -> Said:
    """What comes of ``said``, the words tidied, after ``state``."""
    ledger = around.ledger
    if state.recording is not None:
        return _answered(state, state.recording, said, around)
    if state.editing is not None:
        return _edit_answered(state, state.editing, said, around)
    manual = _manual(said, ledger)
    if manual is not None and not manual.with_trade:
        reply = manual_words(manual.kinds)
        words = (Message(Role.USER, said), Message(Role.ASSISTANT, reply))
        chat = AssistantChat(chat=_with_words(state.chat, words))
        return Said(route=Route.MANUAL, reply=reply, state=chat, manual=manual)
    asked = caught(said, ledger)
    if manual is not None and asked in _MOVED:
        asked = None
    if asked is None and left_asked(said):
        asked = CashAsk.LEFT
    if asked is not None:
        cashed = _cash_answered(state, said, asked, ledger)
        return _with_trade_line(cashed) if _trade_named(said, ledger) else cashed
    done = _modelled(state, said, around, max_steps)
    return done if manual is None else _with_tail(done, manual)


def _manual(said: str, ledger: LedgerPort) -> Statement | None:
    """Money moved said that the assistant does not record, or ``None``.

    A statement that names a coin or share, or says a buy or a sell, is
    one with a trade beside it, which goes on to the model. The ledger's
    assets are asked for only when ``said`` may tell an exchange of moneys,
    or is a statement with no trade seen beside it yet, to know the coins
    and shares it holds; when it cannot be asked, the built-in coins'
    names are used.
    """
    built_in = _built_in_names()
    found = statement(said, built_in)
    if not may_be_exchange(said) and (found is None or found.with_trade):
        return found
    assets = _assets_or_none(ledger)
    return statement(said, (*built_in, *held_names(assets)), money_of_the_ledger(assets))


def _built_in_names() -> tuple[str, ...]:
    return tuple(name for name, _ in names_of(()).built_in)


def _assets_or_none(ledger: LedgerPort) -> tuple[Asset, ...]:
    """The ledger's assets, or none when it cannot be asked."""
    try:
        return ledger.list_assets()
    except LedgerError:
        return ()


def _trade_named(said: str, ledger: LedgerPort) -> bool:
    """Whether ``said``, caught as a question about cash, is said, not asked, and names a coin
    or share: then it may be a trade ("今天现金买了2股KO"). The ledger's assets are asked
    for only for words with no shape of a question or a request."""
    if asks_or_requests(said):
        return False
    held = (*_built_in_names(), *held_names(_assets_or_none(ledger)))
    return names_a_holding(said, held)


def _with_trade_line(done: Said) -> Said:
    """``done``, a question about cash, its reply ending with ``TRADE_AS_CASH_WORDS``."""
    reply = f"{done.reply}\n{TRADE_AS_CASH_WORDS}"
    items = (*done.state.chat.items[:-1], Message(Role.ASSISTANT, reply))
    chat = Chat(items=items, proposals=done.state.chat.proposals)
    return replace(done, reply=reply, state=replace(done.state, chat=chat))


def _cash_answered(state: AssistantChat, said: str, asked: CashAsk, ledger: LedgerPort) -> Said:
    """A question about cash, answered with the ledger's balances or truthfully without."""
    seen = look_up(ledger)
    if seen.balances is not None:
        moneys = tuple(
            (word, row.code) for row in seen.balances.balances for word in (row.code, row.name)
        )
        seen = replace(seen, named=named_money(said, moneys))
    reply, seen = cash_words(asked, seen)
    words = (Message(Role.USER, said), Message(Role.ASSISTANT, reply))
    chat = AssistantChat(chat=_with_words(state.chat, words))
    return Said(route=Route.CASH, reply=reply, state=chat, cash=asked, cash_seen=seen)


def _with_tail(done: Said, manual: Statement) -> Said:
    """``done``, its reply ending with the money moved to record by hand, and, when no
    trade was recorded either, a line saying so: never half of it done unsaid."""
    lines = [manual_tail(manual.kinds)]
    recorded = done.recorded is not None and done.recorded.ending is not RecordEnding.NO_TRADE
    if not recorded:
        lines.append(NOT_RECORDED_EITHER)
    reply = "\n".join((done.reply, *lines)) if done.reply else "\n".join(lines)
    items = done.state.chat.items
    if items and items[-1] == Message(Role.ASSISTANT, done.reply):
        items = (*items[:-1], Message(Role.ASSISTANT, reply))
    else:
        items = (*items, Message(Role.ASSISTANT, "\n".join(lines)))
    chat = Chat(items=items, proposals=done.state.chat.proposals)
    return replace(done, reply=reply, state=replace(done.state, chat=chat), manual=manual)


def _modelled(state: AssistantChat, said: str, around: _Around, max_steps: int) -> Said:
    """What comes of ``said`` handed to the model that chooses tools."""
    model, ledger, now, zone = around.model, around.ledger, around.now, around.zone
    turn = take_turn(
        state.chat, said, model=model, ledger=ledger, now=now, zone=zone, max_steps=max_steps
    )
    turn, seen = _cash_checked(turn, ledger, around.raw_text)
    if seen is not None:
        return Said(
            route=Route.MODEL,
            reply=turn.reply,
            state=AssistantChat(chat=turn.chat),
            turn=turn,
            cash_seen=seen,
        )
    if turn.ending is Ending.EDITING:
        return _edit_begun(turn, said, around)
    if turn.ending is Ending.RECORDING:
        recorded = _begun(said, around)
        reply = reply_for(recorded, begun=True)
        closed = close_recording(turn, recorded.ending.value, reply, _proposals(recorded))
        state = AssistantChat(chat=closed.chat, recording=_waiting(recorded))
        return Said(route=Route.MODEL, reply=reply, state=state, turn=closed, recorded=recorded)
    if turn.ending is Ending.TWO_MISSTEPS:
        edit = first_edit([handled.call for handled in turn.steps[-1].calls])
        if edit is not None:
            return _edit_taken_over(turn, edit, around)
        return _taken_over(turn, said, around)
    return Said(route=Route.MODEL, reply=turn.reply, state=AssistantChat(chat=turn.chat), turn=turn)


def _cash_checked(
    turn: TurnResult, ledger: LedgerPort, raw_text: str | None
) -> tuple[TurnResult, CashSeen | None]:
    """``turn``, its words given way to the program's when they say a figure the user never
    said, and what the ledger said of its cash then; ``None`` when nothing gave way.

    Only the model's own words, with nothing looked up, are checked; a
    turn that looked something up is left as it is. What the user said
    counts both tidied (the chat keeps it so) and, for this sentence, as
    said (``raw_text``), when tidying changed it. The words given are
    ``CASH_WORDS``, or ``WITHHELD_WORDS`` when the ledger has a tool for
    cash balances, which ``CASH_WORDS`` would deny.
    """
    if turn.ending is not Ending.ANSWERED or turn.withheld is not None or turn.lookups:
        return turn, None
    user_said = (*turn.chat.user_said, *((raw_text,) if raw_text is not None else ()))
    withheld = withheld_cash(turn.reply, ledger, user_said)
    if withheld is None:
        return turn, None
    seen = look_up(ledger)
    words = WITHHELD_WORDS if seen.tool is True else CASH_WORDS
    items = (*turn.chat.items[:-1], Message(Role.ASSISTANT, words))
    chat = Chat(items=items, proposals=turn.chat.proposals)
    return replace(turn, reply=words, chat=chat, withheld=withheld), seen


def say_from_reading(
    state: AssistantChat,
    shot: ScreenshotText,
    *,
    model: ModelPort,
    ledger: LedgerPort,
    now: datetime,
    zone: str,
    tuning: Tuning = DEFAULT_TUNING,
    price_gap: Decimal = DEFAULT_PRICE_GAP_TIMES,
    rate_gap: Decimal = DEFAULT_RATE_GAP_PERCENT,
    name_table: bool | None = None,
    names: NamesFile | None = None,
) -> Said:
    """What comes of recording ``shot`` after ``state``, as if the passage were typed.

    The model that chooses tools is not asked. Raises ``ValueError`` when
    something waits for the user's answer: a caller offers no screenshot then.
    ``name_table`` and ``names`` are as for ``say``.
    """
    if state.recording is not None or state.editing is not None:
        raise ValueError("something waits for the user's answer; answer it first")
    around = _Around(
        model,
        ledger,
        now,
        zone,
        tuning,
        gap=price_gap,
        rate_gap=rate_gap,
        name_table=ASSISTANT_NAME_TABLE if name_table is None else name_table,
        names=names,
    )
    recorded = _begun("", around, shot)
    passage = recorded.progress.passage
    reply = reply_for(recorded, begun=True)
    chat = _with_words(state.chat, (Message(Role.USER, passage), Message(Role.ASSISTANT, reply)))
    chat = _with_proposal(chat, recorded)
    return Said(
        route=Route.SCREENSHOT,
        reply=reply,
        state=AssistantChat(chat=chat, recording=_waiting(recorded)),
        recorded=recorded,
    )


def _begun(said: str, around: _Around, shot: ScreenshotText | None = None) -> Recorded:
    """What the user said, word for word, handed to the recording flow; no book is handed in.

    With ``shot``, the passage is the screenshot's text and note joined, and
    ``said`` is not used. The ledger's list of assets is asked for first,
    once, and made into the asset table the flow records with; the proposal
    at the end of this turn uses the same list. When the ledger cannot be
    asked, or prices trades in no money at all, it ends there, and the model
    is asked nothing.
    """
    if shot is not None:
        said = joined_passage(shot.text, shot.note)
    try:
        listed = around.ledger.list_assets()
    except LedgerError as error:
        unbegun = recording.unbegun(said, now=around.now, zone=around.zone, tuning=around.tuning)
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=unbegun, failure=error)
    table = table_of(listed)
    if table is None:
        unbegun = recording.unbegun(said, now=around.now, zone=around.zone, tuning=around.tuning)
        return Recorded(ending=RecordEnding.NO_PRICING_MONEY, progress=unbegun)
    return _onward(_start(said, around, table, shot), around, listed)


def _start(said: str, around: _Around, table: AssetTable, shot: ScreenshotText | None) -> Progress:
    """The recording flow begun the assistant's way, for words typed and a screenshot alike.

    The judging prompt version, the holding back, the picking of an asset from
    the ledger's list, the looking up of an asset's last money in the
    ledger and whether the ledger takes cards with cells left empty are
    named here once, so the two ways cannot drift apart. When the ledger
    takes cards, only which asset and buy or sell are asked (81A section 2
    item 1); otherwise every gap is asked, as before.
    """
    assistant_way = {
        "screen_prompt": ASSISTANT_SCREEN_PROMPT,
        "hold_other_unit": True,
        "pick_assets": ASSISTANT_PICKS_ASSETS,
        "pick_prompt": ASSISTANT_PICK_PROMPT,
        "last_money": last_money_of(around.ledger, around.now),
        "unfinished": around.ledger.takes_unfinished(),
        "name_table": around.name_table,
        "remembered": read_names(around.names).names if around.names is not None else (),
    }
    if shot is None:
        progress = recording.start(
            said,
            around.model,
            now=around.now,
            zone=around.zone,
            assets=table,
            tuning=around.tuning,
            extract_prompt=extract_prompt_for(said, around.chinese),
            **assistant_way,
        )
        if around.raw_text is None:
            return progress
        return replace(progress, raw_text=around.raw_text)
    return start_from_reading(
        shot.reading,
        around.model,
        now=around.now,
        zone=around.zone,
        text=shot.text,
        note=shot.note,
        assets=table,
        tuning=around.tuning,
        extract_prompt=ASSISTANT_EXTRACT_PROMPT,
        **assistant_way,
    )


def _onward(
    progress: Progress, around: _Around, listed: tuple[Asset, ...] | None = None
) -> Recorded:
    """Settled trades go to the ledger; anything else ends where the flow stands.

    ``listed`` is the ledger's list of assets when it was asked for this
    turn; otherwise the proposal asks for it again, as it may have changed
    while a question waited.
    """
    if progress.stage in SETTLED_STAGES:
        return propose(progress, around.ledger, listed, gap=around.gap, rate_gap=around.rate_gap)
    return Recorded(ending=STAGE_ENDINGS[progress.stage], progress=progress)


def _answered(state: AssistantChat, waiting: Progress, said: str, around: _Around) -> Said:
    last_money = last_money_of(around.ledger, around.now)
    progress = recording.answer(waiting, said, around.model, last_money=last_money)
    _remembered(waiting, progress, around.names)
    recorded = _onward(progress, around)
    reply = reply_for(recorded)
    chat = _with_words(state.chat, (Message(Role.USER, said), Message(Role.ASSISTANT, reply)))
    chat = _with_proposal(chat, recorded)
    return Said(
        route=Route.ANSWER,
        reply=reply,
        state=AssistantChat(chat=chat, recording=_waiting(recorded)),
        recorded=recorded,
    )


def _remembered(waiting: Progress, answered: Progress, names: NamesFile | None) -> None:
    """Keep the name a trade's asset cell held and the code answered for it, when the
    question waiting was which asset that trade is, and the answer was a code of the
    ledger's table (``stock_names.worth_remembering``); nothing with no names file.

    Example: "小可" asked about and answered "KO", with KO in the ledger,
    keeps "小可" as KO, on the day of the passage's own moment.
    """
    question = waiting.question
    if names is None or question is None:
        return
    asked = question.asked
    if not isinstance(asked, AskCell) or asked.cell is not Cell.COIN:
        return
    before = waiting.trades[question.trade].draft.coin
    after = answered.trades[question.trade].draft.coin
    if before is None or after is None or before == after:
        return
    kept = worth_remembering(before, after, waiting.passage, waiting.setting.assets)
    if kept is not None:
        remember(names, kept[0], kept[1], waiting.setting.now.date())


def _taken_over(turn: TurnResult, said: str, around: _Around) -> Said:
    """Two wrong steps: what the user said is tried once as a trade to record."""
    recorded = _begun(said, around)
    if recorded.ending in _NOT_A_TRADE:
        state = AssistantChat(chat=turn.chat)
        return Said(
            route=Route.TAKEOVER, reply=turn.reply, state=state, turn=turn, recorded=recorded
        )
    reply = reply_for(recorded, begun=True)
    # The model's apology for its wrong steps gives way to the program's words.
    kept = Chat(items=turn.chat.items[:-1], proposals=turn.chat.proposals)
    chat = _with_proposal(_with_words(kept, (Message(Role.ASSISTANT, reply),)), recorded)
    return Said(
        route=Route.TAKEOVER,
        reply=reply,
        state=AssistantChat(chat=chat, recording=_waiting(recorded)),
        turn=turn,
        recorded=recorded,
    )


def _waiting(recorded: Recorded) -> Progress | None:
    return recorded.progress if recorded.ending is RecordEnding.ASKING else None


def _proposals(recorded: Recorded) -> tuple[str, ...]:
    return recorded.sent.proposals if recorded.sent is not None else ()


def _with_words(chat: Chat, said: tuple[Message, ...]) -> Chat:
    return Chat(items=(*chat.items, *said), proposals=chat.proposals)


def _with_proposal(chat: Chat, recorded: Recorded) -> Chat:
    proposals = _proposals(recorded)
    if not proposals:
        return chat
    return Chat(items=chat.items, proposals=(*chat.proposals, proposals))


def _edit_begun(turn: TurnResult, said: str, around: _Around) -> Said:
    """The model's change or deletion, gone on with by the program."""
    taken = next(call for call in turn.steps[-1].calls if isinstance(call, TakenCall))
    edited = editing.begun(
        taken.call,
        around.ledger,
        turn.chat.user_said,
        now=around.now,
        zone=around.zone,
        raw_text=around.raw_text,
    )
    left = [
        (
            one.call.name,
            _text(one.call.arguments.get("field")),
            _text(one.call.arguments.get("new_value")),
        )
        for one in turn.steps[-1].calls
        if one.call.name in EDIT_TOOLS and one.call is not taken.call
    ]
    reply = edited.reply if not left else f"{edited.reply}\n{not_done_words(left)}"
    proposals = (edited.sent.proposal,) if edited.sent is not None else ()
    closed = close_editing(turn, edited.ending.value, reply, proposals)
    state = AssistantChat(chat=closed.chat, editing=edited.waiting)
    return Said(route=Route.MODEL, reply=reply, state=state, turn=closed, edited=edited)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _edit_answered(state: AssistantChat, waiting: EditWaiting, said: str, around: _Around) -> Said:
    edited = editing.answer(waiting, said, around.ledger, now=around.now, zone=around.zone)
    chat = _with_words(
        state.chat, (Message(Role.USER, said), Message(Role.ASSISTANT, edited.reply))
    )
    if edited.sent is not None:
        chat = Chat(items=chat.items, proposals=(*chat.proposals, (edited.sent.proposal,)))
    return Said(
        route=Route.ANSWER,
        reply=edited.reply,
        state=AssistantChat(chat=chat, editing=edited.waiting),
        edited=edited,
    )


def _edit_taken_over(turn: TurnResult, call: ToolCall, around: _Around) -> Said:
    """Two wrong steps, the last a change or a deletion: the program goes on from that call."""
    user_said = turn.chat.user_said
    edited = editing.taken_over(
        call, around.ledger, user_said, now=around.now, zone=around.zone, raw_text=around.raw_text
    )
    if edited is None:
        return Said(
            route=Route.TAKEOVER, reply=turn.reply, state=AssistantChat(chat=turn.chat), turn=turn
        )
    # The model's apology for its wrong steps gives way to the program's words.
    kept = Chat(items=turn.chat.items[:-1], proposals=turn.chat.proposals)
    chat = _with_words(kept, (Message(Role.ASSISTANT, edited.reply),))
    if edited.sent is not None:
        chat = Chat(items=chat.items, proposals=(*chat.proposals, (edited.sent.proposal,)))
    return Said(
        route=Route.TAKEOVER,
        reply=edited.reply,
        state=AssistantChat(chat=chat, editing=edited.waiting),
        turn=turn,
        edited=edited,
    )
