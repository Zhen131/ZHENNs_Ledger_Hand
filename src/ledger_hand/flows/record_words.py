"""The program's own words to the user once the assistant has recorded what was said.

When the assistant records a trade, the program, not the model, tells the
user how it went: one sentence for every way it can end
(``ENDING_WORDS``, one for each ``RecordEnding``) and one for every reason
a trade was not sent (``LEFT_OUT_WORDS``, one for each ``LeftOut``). A test
walks both enumerations, so a new ending or reason cannot go without a
sentence. They live here, not in the interface, because the try-out script
says them too.

``reply_for`` puts the words together: for a question, the flow's whole
question (its label and sentence, why it is asked again when it is, the
answers to choose from and its notes, one to a line); for an
ending, its sentence, filled in with what the flow or the ledger gave as
the reason, then one line for each trade not sent or turned down. The
figures of a trade are never in these words: the table of what was sent
carries them, laid out by the caller from the proposal itself.

Names defined here: ``ENDING_WORDS``, ``LEFT_OUT_WORDS`` and ``reply_for``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.flows.recorded import LeftOut, LeftOutTrade, Recorded, RecordEnding

ENDING_WORDS: Mapping[RecordEnding, str] = MappingProxyType(
    {
        RecordEnding.ASKING: "{question}",
        RecordEnding.SENT: (
            "Sent to the ledger. It waits there for you to confirm it on the ledger's own page."
        ),
        RecordEnding.LEDGER_REFUSED: (
            "The ledger turned this down, so nothing waits there for you to confirm."
        ),
        RecordEnding.NOTHING_TO_SEND: "Nothing was sent to the ledger.",
        RecordEnding.NO_PRICING_MONEY: (
            "Nothing was sent to the ledger: it has no currency that trades can be priced in. "
            "Please add one in the ledger first."
        ),
        RecordEnding.CANCELLED: "Dropped, as you said: nothing was sent to the ledger.",
        RecordEnding.STOPPED: (
            "Nothing was sent to the ledger: what you said reports only things the ledger "
            "does not record ({reason})."
        ),
        RecordEnding.NO_TRADE: (
            "Nothing was sent to the ledger: no trade was found in what you said."
        ),
        RecordEnding.REFUSED: (
            "Nothing was sent to the ledger: what you said was not read, because {reason}."
        ),
        RecordEnding.MODEL_FAILED: (
            "Nothing was sent to the ledger: the model failed while reading what you said "
            "({reason}). Please try again."
        ),
        RecordEnding.LEDGER_FAILED: (
            "Nothing was sent to the ledger: it could not be asked ({reason}). Please try again."
        ),
    }
)

LEFT_OUT_WORDS: Mapping[LeftOut, str] = MappingProxyType(
    {
        LeftOut.SKIPPED: "Trade {number} was left out, as you said.",
        LeftOut.CANNOT_RECORD: "Trade {number} was not sent: it cannot be recorded ({reason}).",
        LeftOut.DAY_ONLY: (
            "Trade {number} ({code}) was not sent: it has no time of day. Please say this "
            "trade again, with the time it was made."
        ),
        LeftOut.NOT_IN_LEDGER: (
            "Trade {number} was not sent: the ledger has no asset {code} yet. "
            "Please add it in the ledger first."
        ),
        LeftOut.MONEY_TRADED: (
            "Trade {number} was not sent: {code} is a currency in the ledger, and the "
            "assistant does not record an exchange of currencies. Please record it in the "
            "ledger itself."
        ),
        LeftOut.QUOTE_CANNOT_PRICE: (
            "Trade {number} was not sent: the ledger does not price trades in {code}."
        ),
    }
)


def reply_for(recorded: Recorded) -> str:
    """What the program tells the user about ``recorded``."""
    first = ENDING_WORDS[recorded.ending].format(
        question=_question(recorded), code=recorded.missing_money or "", reason=_reason(recorded)
    )
    lines = [first, *(_left_out(trade) for trade in recorded.left_out)]
    lines.extend(_turned_down(recorded))
    return "\n".join(lines)


def _question(recorded: Recorded) -> str:
    question = recorded.question
    if question is None:
        return ""
    again = f"(Asked again: {question.again}) " if question.again is not None else ""
    return "\n".join((again + question.text, *question.choices, *question.notes))


def _reason(recorded: Recorded) -> str:
    progress = recorded.progress
    if recorded.failure is not None:
        return recorded.failure.message
    if recorded.ending is RecordEnding.STOPPED:
        return "; ".join(
            report.kind.value + (f": {report.evidence}" if report.evidence else "")
            for report in progress.stopped
        )
    if recorded.ending is RecordEnding.REFUSED and progress.refused is not None:
        return progress.refused.value
    failure = progress.failure
    if recorded.ending is RecordEnding.MODEL_FAILED and failure is not None:
        detail = str(failure.error) if failure.error is not None else ", ".join(failure.problems)
        return f"{failure.step.value}: {detail}"
    return ""


def _left_out(trade: LeftOutTrade) -> str:
    return LEFT_OUT_WORDS[trade.why].format(
        number=trade.number, code=trade.code or "", reason=trade.reason or ""
    )


def _turned_down(recorded: Recorded) -> list[str]:
    """One line for each trade the ledger's check turned down, with the ledger's sentence."""
    if not recorded.checks:
        return []
    return [
        f"Trade {number}: {check.message}"
        for number, check in zip(recorded.numbers, recorded.checks, strict=True)
        if check.outcome is CheckOutcome.FAILED
    ]
