"""What happens when the person sends a message or presses a button: the words handed to the flows.

Each function here runs when its control is used, before the page is drawn
again, and does one thing:

- ``take_typed``: a message from the chat. While nothing is being recorded,
  it is a new passage (``recording.start``, with the parts the wiring module
  built); when that passage was saved before, the reminder of it comes
  first. While a question waits, it is the answer (``recording.answer``),
  read with the parts as they are now: when the settings were changed
  half-way, the rest of the passage is asked with the new ones
  (``recording.retuned``). Once every trade is settled and the passage is
  neither saved nor discarded, it is not taken: the person is told the last
  passage is not saved yet and given its two choices, so nothing is dropped
  or saved without a word.
- ``save_passage``: makes the records final (``recording.finish``) and
  keeps them in the book (``saving.save``).
- ``discard_passage``: drops the whole passage (``recording.cancel``).
- ``drop_trade``: leaves one trade out (``recording.remove``).
- ``export_saved``: writes the saved trades not exported yet into a new file
  in the exports folder and marks them (``exporting.export``); what became
  of it is kept as the export's note.

What may be done comes from the progress (``can_save``, ``can_cancel``,
``removable``, ``settled``, ``over``); a control used when the flow does not
offer it does nothing. Once a passage is over (saved, discarded, stopped,
refused, without a trade, or failed) nothing of it is kept and the table is
empty again. The program's reply goes into the chat (``sayings``).

Names defined here: ``take_typed``, ``take_text``, ``save_passage``,
``discard_passage``, ``drop_trade`` and ``export_saved``.
"""

from __future__ import annotations

from ledger_hand.flows.exporting import ExportResult, export
from ledger_hand.flows.progress import Progress
from ledger_hand.flows.recording import answer, cancel, finish, remove, retuned, start
from ledger_hand.flows.saving import save
from ledger_hand.ports import StorageError
from ledger_hand.ui import sayings, session
from ledger_hand.ui.session import Note, Place, Speaker, Tone

# How the outcome of an export is shown.
_TONE_OF = {
    ExportResult.EXPORTED: Tone.DONE,
    ExportResult.NOTHING_NEW: Tone.NOTHING,
    ExportResult.REFUSED: Tone.FAILED,
    ExportResult.NOT_WRITTEN: Tone.FAILED,
    ExportResult.NOT_MARKED: Tone.FAILED,
}


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
        reminder = sayings.seen_before(taken)
        if reminder is not None and not taken.over:
            session.say(Speaker.PROGRAM, reminder)
        session.say(Speaker.PROGRAM, sayings.after_start(taken, parts.settings))
    else:
        taken = answer(retuned(current, parts.tuning), text, parts.model)
        session.say(Speaker.PROGRAM, sayings.after_answer(taken, parts.settings))
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
    session.say(Speaker.PROGRAM, sayings.after_answer(dropped, session.parts().settings))
    _keep(dropped)


def drop_trade(number: int) -> None:
    """Leave trade ``number`` (counting from 1) out, if the flow says it can be."""
    current = session.progress()
    if current is None or number not in current.removable:
        return
    left = remove(current, number)
    session.say(Speaker.PROGRAM, sayings.after_removing(number, left))
    _keep(left)


def export_saved() -> None:
    """Export the saved trades not exported yet, if the parts name a folder to export into."""
    parts = session.parts()
    if parts.places is None:
        return
    try:
        outcome = export(
            parts.book,
            parts.places.exports,
            now=parts.clock(),
            zone=parts.zone,
            coins=parts.coins,
        )
    except StorageError as error:
        session.keep_note(Place.EXPORT, Note(Tone.FAILED, sayings.export_failed(error)))
        return
    session.keep_note(Place.EXPORT, Note(_TONE_OF[outcome.result], sayings.exported(outcome)))


def _keep(progress: Progress) -> None:
    """Keep the passage while something can still happen to it; once it is over, nothing."""
    session.keep(None if progress.over else progress)
