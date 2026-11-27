"""What happens on the assistant page when the person types, presses a button or uploads a file.

Each function here runs when its control is used, before the page is drawn
again, and hands the words, the click or the file to the flows; what came
back is kept (``assistant_session``) for the page to draw. Nothing here
decides how a thing said is taken: ``conversation.say`` does.

- ``take_typed`` and ``take_text``: words from the chat, or the answer a
  button stands for (a choice of a question, a trade's number, which amount
  follows), all handed to ``conversation.say`` the same way. The ledger,
  the model, the step limit and the tuning are the parts'; "now" is the
  parts' clock. Proposals sent are kept as cards.
- ``start_new_chat``: forgets the chat (``assistant_session.new_chat``).
- ``check_with_ledger``: asks the ledger page where each proposal of one
  card stands (``standing.standing``) and keeps what came back
  (``assistant_session.keep_checked``); with the ledger page, a card is
  asked only then, never each time the page is drawn.
- ``save_in_demo`` and ``reject_in_demo``: hand a card's proposal to
  ``standing.demo_save`` or ``standing.demo_reject``; when nothing was
  done, the reason is said in the chat.
- ``take_screenshot``, ``keep_box``, ``continue_screenshot`` and
  ``drop_screenshot``: the assistant page's screenshot, kept at
  ``session.ASSISTANT_SPOT``. A file is checked and read by
  ``uploading.read_upload``, as on the Record page; Continue hands the text
  read, as the person left it, and the note to
  ``conversation.say_from_reading``.

Each time the flows hand back what came of a thing said, typed, answered
or from a screenshot, one entry is added to the assistant's record on
this machine (``assistant_record.keep``), at the same moment as was handed
to the flows; the exchange keeps whether it was, or why not, for the page
to say. A record that cannot be added to never stops what was said from
being done. Parts without a data folder keep no record, and the page says
so.

What is said, typed or from a screenshot, is handed the two switches of
matching names of assets (``Parts.name_table``, ``Parts.remember_names``)
and, when answers are remembered, the file of answers in the data folder
for the kind of ledger this tab reaches (``names_file``): the demo
ledger's answers are never used on the ledger page, nor the other way.

Every control hands the flows the parts with the ledger this tab reaches
(``assistant_ledger.parts_now``). Nothing is handed to the flows while the
parts hold no ledger, or carry a refused step
limit: the page then shows why and greys the input out, and a control used
anyway does nothing. With a refused step limit no screenshot is read
either. While the ledger page is chosen but not connected, what is typed
is not handed to the flows and the model is not asked: the page says so,
and how to connect (``assistant_link_words.not_connected``). Each entry of
the record says which kind of ledger it was said to.

Names defined here: ``SentCard``, ``usable``, ``take_typed``, ``take_text``,
``start_new_chat``, ``check_with_ledger``, ``save_in_demo``, ``reject_in_demo``,
``take_screenshot``, ``keep_box``, ``continue_screenshot``,
``drop_screenshot`` and ``names_file``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ledger_hand.flows.asset_names import NamesFile
from ledger_hand.flows.assistant_record import Kept, NotKept, entry_for, keep
from ledger_hand.flows.conversation import Route, Said, ScreenshotText, say, say_from_reading
from ledger_hand.flows.standing import (
    DemoDone,
    DemoOutcome,
    LedgerKind,
    demo_reject,
    demo_save,
    standing,
)
from ledger_hand.flows.uploading import UploadNotRead, read_upload
from ledger_hand.ledger.link_keeper import LinkKeeper
from ledger_hand.settings import SERVICES
from ledger_hand.ui import assistant_ledger, assistant_session, sayings, session
from ledger_hand.ui.assistant_failure_words import (
    Stop,
    demo_words,
    screenshot_not_read,
)
from ledger_hand.ui.assistant_link_words import not_connected
from ledger_hand.ui.assistant_session import Card, NoteTone
from ledger_hand.ui.session import ASSISTANT_SPOT, Box
from ledger_hand.wiring import Parts


@dataclass(frozen=True, kw_only=True)
class SentCard(Card):
    """One thing sent to record trades: a card that holds every proposal it left waiting.

    The ledger keeps each trade it takes as a proposal of its own; the card
    is still one, its ``proposal`` the first, and ``proposals`` all of them
    in the order said. (The session's ``Card`` is left as it is: 68B2 lets
    this batch change only six page files.)
    """

    proposals: tuple[str, ...] = ()


def usable(parts: Parts) -> Stop | None:
    """Why nothing can be handed to the flows with ``parts``, or ``None`` when it can."""
    if parts.ledger is None:
        return Stop.NO_LEDGER
    if parts.steps_refused is not None:
        return Stop.STEPS_REFUSED
    if parts.price_gap_refused is not None:
        return Stop.PRICE_GAP_REFUSED
    if parts.rate_gap_refused is not None:
        return Stop.RATE_GAP_REFUSED
    if parts.names_refused is not None:
        return Stop.NAMES_REFUSED
    return None


def names_file(parts: Parts) -> NamesFile | None:
    """The file of the user's answers for the kind of ledger the parts reach, or ``None``
    when answers are not remembered, or the parts keep no data folder."""
    if not parts.remember_names or parts.places is None:
        return None
    return NamesFile(parts.places.asset_names, parts.ledger_kind or LedgerKind.DEMO)


def take_typed(key: str) -> None:
    """Take what was just sent from the chat input under ``key``."""
    text = session.typed(key)
    if text is not None:
        take_text(text)


def take_text(text: str) -> None:
    """Hand ``text`` to the assistant, and keep what came of it."""
    parts = assistant_ledger.parts_now()
    if usable(parts) is not None or parts.ledger is None:
        return
    if not assistant_ledger.page_connected(parts):
        assistant_session.add_exchange(words=text, note=_not_connected(), tone=NoteTone.FAILED)
        return
    if session.reading(ASSISTANT_SPOT) is not None:
        assistant_session.add_exchange(words=text, note=sayings.screenshot_waiting())
        return
    now = parts.clock()
    said = say(
        assistant_session.chat(),
        text,
        model=parts.model,
        ledger=parts.ledger,
        now=now,
        zone=parts.zone,
        max_steps=parts.assistant_steps,
        tuning=parts.tuning,
        price_gap=parts.price_gap,
        rate_gap=parts.rate_gap,
        name_table=parts.name_table,
        names=names_file(parts),
    )
    _kept(text, said, now)


def _not_connected() -> str:
    """What is said when the ledger page is chosen but not connected."""
    found = assistant_ledger.keeper()
    if not isinstance(found, LinkKeeper):
        return not_connected(None, None, None)
    return not_connected(found.state(), found.port, found.page_port)


def _recorded(words: str, said: Said, now: datetime) -> Kept | NotKept:
    """Add what came of ``words`` to the assistant's record, where the parts keep it."""
    parts = assistant_ledger.parts_now()
    settings = parts.settings
    service = SERVICES.get(settings.plug)
    entry = entry_for(
        said,
        words=words,
        at=now,
        model=settings.model,
        vision_model=settings.vision_model if said.route is Route.SCREENSHOT else None,
        ledger=parts.ledger_kind or LedgerKind.DEMO,
        plug=settings.plug.value,
        service=None if service is None else service.name,
        address=settings.base_url,
    )
    return keep(parts.places.assistant_record if parts.places is not None else None, entry)


def _kept(words: str, said: Said, now: datetime) -> None:
    """Keep what came of ``words``, and a card for the proposal it sent, if it sent one."""
    assistant_session.keep_chat(said.state)
    kept = _recorded(words, said, now)
    exchange = assistant_session.add_exchange(words=words, said=said, kept=kept)
    if said.sent is not None:
        trades = said.sent.trades
        holds = f"{trades} trade{'s' if trades != 1 else ''} to record"
        proposals = said.sent.proposals
        assistant_session.add_card(
            SentCard(
                proposal=proposals[0],
                exchange=exchange.number,
                holds=holds,
                proposals=proposals,
            )
        )
    edit_sent = said.edit_sent
    if edit_sent is not None:
        holds = f"{edit_sent.kind.value} of trade {edit_sent.trade}"
        assistant_session.add_card(
            Card(proposal=edit_sent.proposal, exchange=exchange.number, holds=holds)
        )


def start_new_chat() -> None:
    """Forget the chat; a question left unanswered is dropped with it."""
    assistant_session.new_chat()


def check_with_ledger(proposals: tuple[str, ...]) -> None:
    """Ask the ledger where each of ``proposals`` stands now, and keep what it said."""
    ledger = assistant_ledger.parts_now().ledger
    if ledger is None:
        return
    for proposal in proposals:
        assistant_session.keep_checked(standing(ledger, proposal))


def save_in_demo(proposal: str) -> None:
    """Save ``proposal`` in the demo ledger; say why not when it was not."""
    ledger = session.parts().ledger
    if ledger is not None:
        _said_unless_done(demo_save(ledger, proposal))


def reject_in_demo(proposal: str) -> None:
    """Reject ``proposal`` in the demo ledger; say why not when it was not."""
    ledger = session.parts().ledger
    if ledger is not None:
        _said_unless_done(demo_reject(ledger, proposal))


def _said_unless_done(done: DemoDone) -> None:
    if done.outcome is not DemoOutcome.DONE:
        assistant_session.add_exchange(note=demo_words(done), tone=NoteTone.FAILED)


def take_screenshot(key: str, read_key: str, note_key: str) -> None:
    """Take the file just uploaded under ``key``: have it checked and read, or say why not."""
    data = session.uploaded(key)
    session.next_upload_round(ASSISTANT_SPOT)
    state = assistant_session.chat()
    waiting = state.recording is not None or state.editing is not None
    if data is None or waiting or session.reading(ASSISTANT_SPOT) is not None:
        return
    parts = session.parts()
    if parts.steps_refused is not None:
        return
    outcome = read_upload(
        data, parts.settings, vision_model=parts.vision_model, check=parts.vision_check
    )
    if isinstance(outcome, UploadNotRead):
        _fill_boxes(read_key, note_key, "")
        sentence = screenshot_not_read(outcome, parts.settings)
        assistant_session.add_exchange(note=sentence, tone=NoteTone.FAILED)
        return
    session.keep_reading(outcome.reading, ASSISTANT_SPOT)
    _fill_boxes(read_key, note_key, outcome.reading.text)
    assistant_session.add_exchange(note=sayings.screenshot_read())


def keep_box(box: Box, key: str) -> None:
    """Keep what the box under ``key`` holds now as ``box``'s text, on the assistant page."""
    typed = session.typed(key)
    if typed is not None:
        session.keep_box_text(box, typed, ASSISTANT_SPOT)


def continue_screenshot(read_key: str, note_key: str) -> None:
    """Record the text read, as it stands, and the note, as if the person had typed them."""
    reading = session.reading(ASSISTANT_SPOT)
    parts = assistant_ledger.parts_now()
    state = assistant_session.chat()
    waiting = state.recording is not None or state.editing is not None
    if reading is None or waiting or usable(parts) is not None or parts.ledger is None:
        return
    if not assistant_ledger.page_connected(parts):
        return
    keep_box(Box.READ, read_key)
    keep_box(Box.NOTE, note_key)
    shot = ScreenshotText(
        reading=reading,
        text=session.box_text(Box.READ, ASSISTANT_SPOT),
        note=session.box_text(Box.NOTE, ASSISTANT_SPOT),
    )
    now = parts.clock()
    said = say_from_reading(
        state,
        shot,
        model=parts.model,
        ledger=parts.ledger,
        now=now,
        zone=parts.zone,
        tuning=parts.tuning,
        price_gap=parts.price_gap,
        rate_gap=parts.rate_gap,
        name_table=parts.name_table,
        names=names_file(parts),
    )
    session.keep_reading(None, ASSISTANT_SPOT)
    _fill_boxes(read_key, note_key, "")
    _kept(said.recorded.progress.passage if said.recorded is not None else "", said, now)


def drop_screenshot(read_key: str, note_key: str) -> None:
    """Drop the screenshot read, if one waits; nothing is sent."""
    if session.reading(ASSISTANT_SPOT) is None:
        return
    session.keep_reading(None, ASSISTANT_SPOT)
    _fill_boxes(read_key, note_key, "")
    assistant_session.add_exchange(note=sayings.screenshot_dropped())


def _fill_boxes(read_key: str, note_key: str, text: str) -> None:
    """Put ``text`` in the box of the text read and empty the note, kept and drawn alike."""
    session.keep_box_text(Box.READ, text, ASSISTANT_SPOT)
    session.keep_box_text(Box.NOTE, "", ASSISTANT_SPOT)
    session.put(read_key, text)
    session.put(note_key, "")
