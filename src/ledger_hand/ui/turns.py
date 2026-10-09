"""What happens when the person sends a message or presses a button: the words handed to the flows.

Each function here runs when its control is used, before the page is drawn
again, and does one thing:

- ``take_typed``: a message from the chat. While nothing is being recorded,
  it is a new passage (``recording.start``, with the parts the wiring module
  built); while a question waits, it is the answer (``recording.answer``).
  Once every trade is settled and the passage is neither saved nor
  discarded, it is not taken: the person is told the last passage is not
  saved yet and given its two choices, so nothing is dropped or saved
  without a word.
- ``save_passage``: makes the records final (``recording.finish``) and
  keeps them in the book (``saving.save``).
- ``discard_passage``: drops the whole passage (``recording.cancel``).
- ``drop_trade``: leaves one trade out (``recording.remove``).

What may be done comes from the progress (``can_save``, ``can_cancel``,
``removable``, ``settled``, ``over``); a control used when the flow does not
offer it does nothing. Once a passage is over (saved, discarded, stopped,
refused, without a trade, or failed) nothing of it is kept and the table is
empty again. The program's reply goes into the chat (``sayings``).

Names defined here: ``take_typed``, ``take_text``, ``save_passage``,
``discard_passage`` and ``drop_trade``.
"""

from __future__ import annotations

from ledger_hand.flows.progress import Progress
from ledger_hand.flows.recording import answer, cancel, finish, remove, start
from ledger_hand.flows.saving import save
from ledger_hand.ports import StorageError
from ledger_hand.ui import sayings, session
from ledger_hand.ui.session import Speaker


def take_typed(key: str) -> None:
    """Take what was just sent from the chat input under ``key``."""
    text = session.typed(key)
    if text is not None:
        take_text(text)


def take_text(text: str) -> None:
    """Take ``text`` as a new passage, or as the answer to the question waiting."""
    session.say(Speaker.PERSON, text)
    current = session.progress()
    if current is not None and current.settled:
        session.say(Speaker.PROGRAM, sayings.not_taken_yet(current))
        return
    parts = session.parts()
    if current is None:
        try:
            taken = start(
                text,
                parts.model,
                now=parts.clock(),
                zone=parts.zone,
                coins=parts.coins,
                tuning=parts.tuning,
                book=parts.book,
            )
        except StorageError as error:
            session.say(Speaker.PROGRAM, sayings.book_failed(error))
            return
        session.say(Speaker.PROGRAM, sayings.after_start(taken))
    else:
        taken = answer(current, text, parts.model)
        session.say(Speaker.PROGRAM, sayings.after_answer(taken))
    _keep(taken)


def save_passage() -> None:
    """Keep the records of the passage in the book, if the flow says they can be saved."""
    current = session.progress()
    if current is None or not current.can_save:
        return
    parts = session.parts()
    try:
        kept = save(finish(current), parts.book, now=parts.clock())
    except StorageError as error:
        session.say(Speaker.PROGRAM, sayings.not_saved(error))
        return
    session.say(Speaker.PROGRAM, sayings.saved(len(kept.trades)))
    session.keep(None)


def discard_passage() -> None:
    """Drop the whole passage, if the flow says it can be dropped now."""
    current = session.progress()
    if current is None or not current.can_cancel:
        return
    dropped = cancel(current)
    session.say(Speaker.PROGRAM, sayings.after_answer(dropped))
    _keep(dropped)


def drop_trade(number: int) -> None:
    """Leave trade ``number`` (counting from 1) out, if the flow says it can be."""
    current = session.progress()
    if current is None or number not in current.removable:
        return
    left = remove(current, number)
    session.say(Speaker.PROGRAM, sayings.after_removing(number, left))
    _keep(left)


def _keep(progress: Progress) -> None:
    """Keep the passage while something can still happen to it; once it is over, nothing."""
    session.keep(None if progress.over else progress)
