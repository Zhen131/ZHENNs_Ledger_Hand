"""One plain sentence for every way the assistant page can fail: what happened, and what to do.

The assistant page shows no raw error either. Beside the program's reply it
says each failure that reply rests on, looked up here:

- the six kinds of model failure, as the Record page says them
  (``failure_words.model_trouble``), and a recording that failed because of
  the model (``failure_words.model_failed``);
- every kind of ledger failure (``LEDGER_FAILURES``, one sentence for each
  ``LedgerErrorKind``), with the ledger's own words after it;
- the ways the page itself stops (``STOPS``, one sentence for each
  ``Stop``): the step limit reached, the program's taking over that still
  found nothing, no ledger connected, the cloud plug, which the assistant
  does not run on, and a step limit set in the environment that was
  refused;
- a demo save or reject that did nothing (``DEMO_WORDS``, one for each
  ``standing.DemoOutcome`` that is not done);
- every way a screenshot is not read, as the Record page says them
  (``failure_words.screenshot_not_read``), except one. When the model
  server could not be asked whether it has the vision model because its
  answer could not be read, or it turned the question down with status
  400, the Record page passes on the general sentence, which tells the
  person to put the passage another way. Here the page says what is meant
  (``VISION_LIST_UNCLEAR``): the server's answer was not clear, so check
  that it is running and that the vision model is in its list.

The Record page's sentences are not changed by this file. A test walks every
table here against its enumeration, so a new kind cannot go without one.

Names defined here: ``Stop``, ``STOPS``, ``LEDGER_FAILURES``, ``DEMO_WORDS``,
``VISION_LIST_UNCLEAR``, ``ledger_trouble``, ``stop_words``,
``failure_lines``, ``demo_words`` and ``screenshot_not_read``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from types import MappingProxyType

from ledger_hand.assistant.outcome import Ending
from ledger_hand.flows.conversation import Route, Said
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.flows.standing import DemoDone, DemoOutcome
from ledger_hand.flows.uploading import UploadNotRead, UploadProblem
from ledger_hand.ports import LedgerError, LedgerErrorKind, ModelError, ModelErrorKind
from ledger_hand.settings import ASSISTANT_STEPS_VARIABLE, ModelSettings, Plug, Variable
from ledger_hand.ui import failure_words


class Stop(enum.Enum):
    """Why the assistant page stopped, or will not start, by itself."""

    STEP_LIMIT = "the model was asked as often as one turn allows"
    TAKEOVER_FAILED = "the program took over and still could not do it"
    NO_LEDGER = "no ledger is connected"
    CLOUD_PLUG = "the cloud plug is set, and the assistant runs on the local plug only"
    STEPS_REFUSED = "the setting of how many steps the assistant may take was refused"


# {steps} is how many times the model may be asked in one turn.
STOPS: Mapping[Stop, str] = MappingProxyType(
    {
        Stop.STEP_LIMIT: (
            "The model was asked {steps} times, as many as one turn allows, without finishing; "
            "nothing more was done. Say it again more simply, or allow more steps with "
            f"{ASSISTANT_STEPS_VARIABLE} and start the program again."
        ),
        Stop.TAKEOVER_FAILED: (
            "The model went wrong twice in a row, and the program could not go on from what "
            "you said either, so nothing was done. Say it another way."
        ),
        Stop.NO_LEDGER: (
            "No ledger is connected, so the assistant cannot look anything up or send "
            "anything. Nothing you type here is sent."
        ),
        Stop.CLOUD_PLUG: (
            "Cloud models are not supported for the assistant yet: it runs on the local "
            f"plug only. Set {Variable.PLUG.value} to {Plug.LOCAL.value} on the Settings page "
            "to use it. Nothing typed here is sent."
        ),
        Stop.STEPS_REFUSED: (
            "The assistant cannot start: {detail}. Correct "
            f"{ASSISTANT_STEPS_VARIABLE}, or remove it to use its default, then start the "
            "program again. Nothing typed here is sent."
        ),
    }
)

LEDGER_FAILURES: Mapping[LedgerErrorKind, str] = MappingProxyType(
    {
        LedgerErrorKind.UNREACHABLE: (
            "The ledger could not be reached, so nothing was looked up or sent. Check that "
            "it is running, then try again."
        ),
        LedgerErrorKind.UNKNOWN_ASSET: (
            "The ledger does not know an asset it was asked about, so nothing was done with it."
        ),
        LedgerErrorKind.NOT_FOUND: (
            "The ledger has no such trade or proposal, so nothing was done with it."
        ),
        LedgerErrorKind.ASSET_IS_CURRENCY: (
            "The ledger lists no trades by a currency, so nothing was looked up."
        ),
        LedgerErrorKind.TIMED_OUT: (
            "The ledger did not answer in time. Anything sent may already be waiting "
            "there, so nothing was sent again: please look at the ledger's pending list."
        ),
        LedgerErrorKind.RESULT_UNKNOWN: (
            "The ledger page may have been reloaded, so the result of this one can no "
            "longer be looked up. That does not mean it was not saved: please look at "
            "the ledger."
        ),
        LedgerErrorKind.OTHER: "The ledger reported a failure of its own; nothing was done.",
    }
)

DEMO_WORDS: Mapping[DemoOutcome, str] = MappingProxyType(
    {
        DemoOutcome.NOT_DEMO: (
            "This works on the demo ledger only, so nothing was saved or rejected. Confirm "
            "it on the ledger's own page."
        ),
        DemoOutcome.FAILED: "The demo ledger did not do it.",
    }
)

VISION_LIST_UNCLEAR = (
    "The model server at {address} did not answer clearly whether it has the vision model "
    "{model}, so the screenshot was not sent. That is the server's side, not your "
    "screenshot: check that the server is running, and that {model} is in its list of "
    "models (ollama list), then try again."
)


def ledger_trouble(error: LedgerError) -> str:
    """The sentence for a ledger's failure, with the ledger's own words after it."""
    return f"{LEDGER_FAILURES[error.kind]} ({error.message})"


def stop_words(stop: Stop, steps: int, detail: str = "") -> str:
    """The sentence for ``stop``; ``steps`` is how many times one turn may ask the model,
    ``detail`` the settings' own words on a refused setting."""
    return STOPS[stop].format(steps=steps, detail=detail)


def failure_lines(said: Said, settings: ModelSettings, steps: int) -> tuple[str, ...]:
    """Every failure ``said`` rests on, one sentence each, in the order they came."""
    lines: list[str] = []
    turn = said.turn
    if turn is not None and turn.failure is not None:
        lines.append(_trouble(turn.failure, settings))
    if turn is not None and turn.ending is Ending.STEP_LIMIT:
        lines.append(stop_words(Stop.STEP_LIMIT, steps))
    recorded = said.recorded
    if recorded is not None:
        if recorded.failure is not None:
            lines.append(ledger_trouble(recorded.failure))
        failure = recorded.progress.failure
        if recorded.ending is RecordEnding.MODEL_FAILED and failure is not None:
            lines.append(failure_words.model_failed(failure, settings))
        question = recorded.question
        if question is not None and question.model_failure is not None:
            lines.append(failure_words.model_kind_trouble(question.model_failure, settings))
    if said.edited is not None and said.edited.failure is not None:
        lines.append(ledger_trouble(said.edited.failure))
    if said.route is Route.TAKEOVER and not said.well_ended and said.edited is None:
        lines.append(stop_words(Stop.TAKEOVER_FAILED, steps))
    return tuple(lines)


def _trouble(error: ModelError | LedgerError, settings: ModelSettings) -> str:
    if isinstance(error, LedgerError):
        return ledger_trouble(error)
    return failure_words.model_trouble(error, settings)


def demo_words(done: DemoDone) -> str:
    """What is said when a demo save or reject did nothing, with the ledger's words."""
    said = DEMO_WORDS[done.outcome]
    return said if done.failure is None else f"{said} {ledger_trouble(done.failure)}"


def screenshot_not_read(outcome: UploadNotRead, settings: ModelSettings) -> str:
    """What is said when a screenshot was not read: as the Record page says it, but one."""
    error = outcome.error
    unclear = error is not None and (
        error.kind is ModelErrorKind.MALFORMED_REPLY
        or (error.kind is ModelErrorKind.SERVER_ERROR and error.status == 400)
    )
    if outcome.problem is UploadProblem.VISION_MODEL_UNCHECKED and unclear:
        return VISION_LIST_UNCLEAR.format(address=settings.base_url, model=settings.vision_model)
    return failure_words.screenshot_not_read(outcome, settings)
