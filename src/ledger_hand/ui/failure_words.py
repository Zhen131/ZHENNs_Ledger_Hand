"""One plain sentence for every way something can fail: what happened, and what you can do.

The interface never shows a failure as a raw error. Each kind of failure is
looked up here and said in English: the six kinds of model failure, a reply
that cannot be read as a table, a passage that is not sent (empty, too long,
not valid text), a setting or a change refused, every kind of storage
failure (a book written by a newer version among them), an export refused
and an export file not written or not marked. Every enumeration of kinds
has an entry for each of its members, and a test walks them, so a new kind
cannot go without a sentence.

A model failure of one kind may be said differently for each status code
the server answered with: ``MODEL_FAILURES_BY_STATUS`` is looked up first,
by kind and status. It holds the statuses with which a cloud service turns
a call down as a server error: a key refused (401, 403) and a request
refused (400), the latter with the start of what the server answered. A
rate-limited call whose server said how long to wait is said with that wait
(``RATE_LIMITED_FOR``).

What a sentence fills in comes from the settings the parts were built from
(the address, the model's name, the time allowed) or from the failure itself
(a status code, the start of the server's answer, the wait it asked for, a
file's path, a reason). The key never appears: the settings keep it hidden,
no sentence names it, and the start of a server's answer has the key hidden
once more here, in every form a server may write it back, although the
plugs never let it through.

Names defined here: ``MODEL_FAILURES``, ``MODEL_FAILURES_BY_STATUS``,
``RATE_LIMITED_FOR``, ``REPLY_UNREADABLE``, ``PASSAGE_REFUSALS``, ``STORAGE_FAILURES``,
``ASSEMBLY_FAILURES``, ``WRITE_FAILURES``, ``model_failed``,
``model_trouble``, ``passage_refused``, ``book_trouble``,
``assembly_failed``, ``export_refused``, ``export_not_written`` and
``export_not_marked``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType

from ledger_hand.core.ledger_limits import RAW_TEXT_MAX_LENGTH
from ledger_hand.export.backup import ExportIssue
from ledger_hand.extraction.passage_check import PassageProblem
from ledger_hand.flows.export_file import WriteProblem
from ledger_hand.flows.progress import Failure
from ledger_hand.llm.error_text import hide
from ledger_hand.ports import ModelError, ModelErrorKind, StorageError, StorageErrorKind
from ledger_hand.settings import DATA_DIRECTORY_VARIABLE, ModelSettings, Variable
from ledger_hand.ui.setting_text import written
from ledger_hand.wiring import AssemblyError, AssemblyProblem

# What went wrong with the model, and what can be done. {address} is where
# the model was asked, {model} its name, {seconds} the time allowed,
# {status} the server's status code, when it gave one, {said} the start of
# what the server answered, when there was something, and {wait} the
# seconds the server asked to wait.
MODEL_FAILURES: Mapping[ModelErrorKind, str] = MappingProxyType(
    {
        ModelErrorKind.UNREACHABLE: (
            "No model answered at {address}. If the model runs on this machine, check that "
            "Ollama is running; otherwise check the address on the Settings page."
        ),
        ModelErrorKind.TIMED_OUT: (
            "No whole reply came within {seconds} seconds. The first call after the model "
            "starts has to load it into memory, which can be slow. Try again, or allow more "
            "time on the Settings page."
        ),
        ModelErrorKind.MODEL_NOT_FOUND: (
            "The server at {address} has no model named {model}. Check the name on the "
            "Settings page, or install the model with Ollama (ollama pull {model})."
        ),
        ModelErrorKind.RATE_LIMITED: (
            "The model server turned the call away because it was called too often. Wait a "
            "little, then try again."
        ),
        ModelErrorKind.SERVER_ERROR: (
            "The model server reported an error of its own{status}. Try again; if it keeps "
            "failing, look at the server's own log."
        ),
        ModelErrorKind.MALFORMED_REPLY: (
            "The model answered, but not in the agreed form, so its reply could not be used. "
            "Try again, or put the passage another way."
        ),
    }
)

# The key is set in the environment only, so that is where it is put right.
_KEY_REFUSED = (
    "The model server at {address} did not take the key{status}. Check "
    f"{Variable.KEY.value} in the environment, where the key is set, and that it may use "
    "{model}; then start the program again."
)

# The same, said for one status code of one kind; looked up before the above.
MODEL_FAILURES_BY_STATUS: Mapping[tuple[ModelErrorKind, int], str] = MappingProxyType(
    {
        (ModelErrorKind.SERVER_ERROR, 401): _KEY_REFUSED,
        (ModelErrorKind.SERVER_ERROR, 403): _KEY_REFUSED,
        (ModelErrorKind.SERVER_ERROR, 400): (
            "The model server at {address} turned the request down as it was sent{status}."
            "{said} Check the model's name on the Settings page. A service that does not "
            "take the reply table this program sends turns every call down this way."
        ),
    }
)

# Rate limited, when the server said how long to wait.
RATE_LIMITED_FOR = (
    "The model server turned the call away because it was called too often, and asked to "
    "wait {wait} seconds. Wait that long, then try again."
)

# The model answered, but no reply could be read as the table it was asked for.
REPLY_UNREADABLE = (
    "The model's replies could not be read as the table it was asked for, so they could not "
    "be used. Try again, or put the passage another way."
)

# Why a passage was not sent. The empty one is said as it always was.
PASSAGE_REFUSALS: Mapping[PassageProblem, str] = MappingProxyType(
    {
        PassageProblem.EMPTY: "the passage is empty",
        PassageProblem.TOO_LONG: (
            f"the passage is longer than the {RAW_TEXT_MAX_LENGTH:,} characters the ledger "
            "keeps as the original text. Split it into shorter passages and send them one "
            "at a time"
        ),
        PassageProblem.NOT_VALID_TEXT: (
            "the passage holds a character that is not valid text. Type it again, or paste "
            "it from somewhere else"
        ),
    }
)

# What happened to the book, and what can be done. The book is left as it is.
_ELSEWHERE = f"or point {DATA_DIRECTORY_VARIABLE} at another folder and start the program again"
STORAGE_FAILURES: Mapping[StorageErrorKind, str] = MappingProxyType(
    {
        StorageErrorKind.NEWER_VERSION: (
            "The book was written by a newer version of this program, so this one does not "
            f"touch it. Use the newer version, {_ELSEWHERE}."
        ),
        StorageErrorKind.NOT_A_DATABASE: (
            "The book's file is not a database, so it was left as it is. Move that file "
            f"away, {_ELSEWHERE}."
        ),
        StorageErrorKind.NOT_THIS_PROGRAMS: (
            "The book's file is a database, but not this program's book, so it was left as "
            f"it is. Move that file away, {_ELSEWHERE}."
        ),
        StorageErrorKind.DAMAGED: (
            "The book is damaged, so the program does not write to it. Keep a copy of the "
            f"file as it is, then move it away, {_ELSEWHERE}."
        ),
        StorageErrorKind.LOCKED: (
            "The book is in use by another program and stayed busy. Close the other "
            "program, then try again."
        ),
        StorageErrorKind.INACCESSIBLE: (
            "The book or its folder cannot be made, read or written: no permission, a "
            "read-only folder or a full disk. Check the folder, then try again."
        ),
        StorageErrorKind.CONFLICT: (
            "What was asked clashes with what the book holds, so the book was not changed. "
            "Try again."
        ),
        StorageErrorKind.UNEXPECTED: (
            "The book failed in a way this program does not know, so the book was not "
            "changed. Try again."
        ),
    }
)

# Why the parts could not be built, and what can be done.
ASSEMBLY_FAILURES: Mapping[AssemblyProblem, str] = MappingProxyType(
    {
        AssemblyProblem.SETTING_REFUSED: (
            "Correct that environment variable, or remove it to use its default, then "
            "start the program again."
        ),
        AssemblyProblem.CHANGE_REFUSED: "The settings were not changed.",
        AssemblyProblem.NO_ZONE_NAME: (
            "Give the machine a named time zone, such as Europe/Budapest, then start the "
            "program again."
        ),
    }
)

# Why an export file was not written, and what can be done.
WRITE_FAILURES: Mapping[WriteProblem, str] = MappingProxyType(
    {
        WriteProblem.NAME_TAKEN: (
            "A file of that name is already there and was left as it is; the name carries "
            "the second it was made, so press Export again in a moment."
        ),
        WriteProblem.CANNOT_WRITE: (
            "The file could not be written. Check that the exports folder can be written, "
            "then press Export again."
        ),
    }
)


def model_failed(failure: Failure, settings: ModelSettings) -> str:
    """What is said when a passage ended because the model failed, or its replies were unusable."""
    said = f"The model gave no usable reply while {failure.step.value}, so nothing was recorded."
    if failure.error is None:
        return f"{said} {REPLY_UNREADABLE}"
    return f"{said} {model_trouble(failure.error, settings)}"


def model_trouble(error: ModelError, settings: ModelSettings) -> str:
    """The sentence for ``error``: by its kind and status code if there is one, else its kind.

    A rate-limited call whose server said how long to wait is said with the
    wait, in whole seconds, rounded up.
    """
    template = None
    if error.status is not None:
        template = MODEL_FAILURES_BY_STATUS.get((error.kind, error.status))
    if template is None and error.kind is ModelErrorKind.RATE_LIMITED:
        template = None if error.retry_after_seconds is None else RATE_LIMITED_FOR
    if template is None:
        template = MODEL_FAILURES[error.kind]
    return template.format(
        address=settings.base_url,
        model=settings.model,
        seconds=written(settings.timeout_seconds),
        status="" if error.status is None else f" (status {error.status})",
        said=_said(error, settings),
        wait=_wait(error),
    )


def _said(error: ModelError, settings: ModelSettings) -> str:
    """The start of what the server answered, as a sentence; nothing when it sent nothing."""
    if not error.snippet:
        return ""
    return f' Its answer began: "{hide(error.snippet, settings.api_key)}".'


def _wait(error: ModelError) -> str:
    """The wait the server asked for, in whole seconds rounded up, at least 1."""
    if error.retry_after_seconds is None:
        return ""
    return written(max(1, math.ceil(error.retry_after_seconds)))


def passage_refused(problem: PassageProblem) -> str:
    """What is said when a passage was not sent to the model."""
    return f"Nothing was sent to the model: {PASSAGE_REFUSALS[problem]}."


def book_trouble(error: StorageError) -> str:
    """What happened to the book and what can be done, with the book's own words and its path."""
    return f"{STORAGE_FAILURES[error.kind]} ({error.message})"


def assembly_failed(error: AssemblyError) -> str:
    """What is said when the parts could not be built, or a change could not be applied.

    A refused change names the setting and its rule; anything else says the
    program cannot start, and why.
    """
    if error.problem is AssemblyProblem.CHANGE_REFUSED:
        return f"Not applied: {error.detail}. {ASSEMBLY_FAILURES[error.problem]}"
    return f"The program cannot start: {error}. {ASSEMBLY_FAILURES[error.problem]}"


def export_refused(issues: Sequence[ExportIssue]) -> str:
    """Every reason an export was refused, one to a line; nothing was written or marked."""
    lines = [
        "Nothing was exported and nothing was marked as exported: the saved trades cannot "
        "be written as a file as they are."
    ]
    lines += [f"    {issue.problem.value}: {issue.subject}" for issue in issues]
    return "\n".join(lines)


def export_not_written(problem: WriteProblem, detail: str | None) -> str:
    """What is said when the export file could not be written; nothing was marked."""
    said = f"Nothing was exported and nothing was marked as exported. {WRITE_FAILURES[problem]}"
    return said if not detail else f"{said} ({detail})"


def export_not_marked(path: Path | None, error: StorageError | None) -> str:
    """What is said when the file was written but its trades could not be marked as exported."""
    said = (
        f"The file was written to {path}, but its trades could not be marked as exported, "
        "so the next export writes them again; keep only one of the two files."
    )
    return said if error is None else f"{said} {book_trouble(error)}"
