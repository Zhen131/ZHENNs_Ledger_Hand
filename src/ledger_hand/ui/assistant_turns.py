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

Nothing is handed to the flows while the parts hold no ledger, choose the
cloud plug, or carry a refused step limit: the page then shows why and
greys the input out, and a control used anyway does nothing. With a
refused step limit no screenshot is read either.

Names defined here: ``usable``, ``take_typed``, ``take_text``,
``start_new_chat``, ``save_in_demo``, ``reject_in_demo``,
``take_screenshot``, ``keep_box``, ``continue_screenshot`` and
``drop_screenshot``.
"""

from __future__ import annotations

from datetime import datetime

from ledger_hand.flows.assistant_record import Kept, NotKept, entry_for, keep
from ledger_hand.flows.conversation import Route, Said, ScreenshotText, say, say_from_reading
from ledger_hand.flows.standing import DemoDone, DemoOutcome, demo_reject, demo_save
from ledger_hand.flows.uploading import UploadNotRead, read_upload
from ledger_hand.settings import Plug
from ledger_hand.ui import assistant_session, sayings, session
from ledger_hand.ui.assistant_failure_words import (
    Stop,
    demo_words,
    screenshot_not_read,
)
from ledger_hand.ui.assistant_session import Card, NoteTone
from ledger_hand.ui.session import ASSISTANT_SPOT, Box
from ledger_hand.wiring import Parts


def usable(parts: Parts) -> Stop | None:
    """Why nothing can be handed to the flows with ``parts``, or ``None`` when it can."""
    if parts.ledger is None:
        return Stop.NO_LEDGER
    if parts.settings.plug is Plug.CLOUD:
        return Stop.CLOUD_PLUG
    if parts.steps_refused is not None:
        return Stop.STEPS_REFUSED
    return None


def take_typed(key: str) -> None:
    """Take what was just sent from the chat input under ``key``."""
    text = session.typed(key)
    if text is not None:
        take_text(text)


def take_text(text: str) -> None:
    """Hand ``text`` to the assistant, and keep what came of it."""
    parts = session.parts()
    if usable(parts) is not None or parts.ledger is None:
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
    )
    _kept(text, said, now)


def _recorded(words: str, said: Said, now: datetime) -> Kept | NotKept:
    """Add what came of ``words`` to the assistant's record, where the parts keep it."""
    parts = session.parts()
    entry = entry_for(
        said,
        words=words,
        at=now,
        model=parts.settings.model,
        vision_model=parts.settings.vision_model if said.route is Route.SCREENSHOT else None,
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
        assistant_session.add_card(
            Card(proposal=said.sent.proposal, exchange=exchange.number, holds=holds)
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
    parts = session.parts()
    state = assistant_session.chat()
    waiting = state.recording is not None or state.editing is not None
    if reading is None or waiting or usable(parts) is not None or parts.ledger is None:
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
