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
refused (400), the latter with the start of what the server answered. Next
comes ``MODEL_FAILURES_BY_PLUG``, by kind and the plug the settings choose:
a model the cloud service does not have is not one to install with Ollama.
A rate-limited call whose server said how long to wait is said with that
wait (``RATE_LIMITED_FOR``). A failure known only by its kind, without a
status code or a wait, is looked up the same way (``model_kind_trouble``).

With a cloud plug (cloud, or a service such as deepseek), ``CLOUD_FAILURES``
is looked up before all of these, by kind and status code, then by kind:
it speaks of the service and the internet, not of Ollama, names the
variable that service's key is read from, and says plainly that nothing
was sent to the local model instead. A server error with no status of its
own there (500, 503, 422, none at all) is said as the service's error, not
with the local sentence that sends you to the server's own log. No sentence there quotes what the
service answered: a service may write the key back in a form that cannot
be hidden. A model failure is never followed by a call to another model:
the program says what happened and stops.

An uploaded screenshot that was not read is said by its problem
(``SCREENSHOT_FAILURES``, one sentence for each ``UploadProblem``), with the
file's size and the limit in MB, and the vision model's name. When the
server could not be asked for the vision model, the failure follows, looked
up as above but with the vision model's name in place of the model's. When
the vision model failed while reading, so does the failure, looked up the
same way (``vision_trouble``), except two, which would point the wrong way
for a screenshot, since a picture is sent without a reply table and there is
no passage to put another way: a request turned down with status 400
(``VISION_REFUSED``) and a reply not in the agreed form
(``VISION_MALFORMED``).

What a sentence fills in comes from the settings the parts were built from
(the address, the model's name, the time allowed) or from the failure itself
(a status code, the start of the server's answer, the wait it asked for, a
file's path, a reason). The key never appears: the settings keep it hidden,
no sentence names it, and the start of a server's answer has the key hidden
once more here, in every form a server may write it back, although the
plugs never let it through.

Names defined here: ``MODEL_FAILURES``, ``MODEL_FAILURES_BY_STATUS``,
``MODEL_FAILURES_BY_PLUG``, ``CLOUD_FAILURES``, ``RATE_LIMITED_FOR``, ``REPLY_UNREADABLE``,
``PASSAGE_REFUSALS``, ``STORAGE_FAILURES``, ``ASSEMBLY_FAILURES``,
``WRITE_FAILURES``, ``SCREENSHOT_FAILURES``, ``VISION_REFUSED``,
``VISION_MALFORMED``, ``model_failed``, ``model_trouble``,
``model_kind_trouble``, ``screenshot_not_read``, ``vision_trouble``,
``passage_refused``, ``book_trouble``,
``assembly_failed``, ``export_refused``, ``export_not_written`` and
``export_not_marked``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from ledger_hand.core.ledger_limits import RAW_TEXT_MAX_LENGTH
from ledger_hand.export.backup import ExportIssue
from ledger_hand.extraction.passage_check import PassageProblem
from ledger_hand.flows.export_file import WriteProblem
from ledger_hand.flows.progress import Failure
from ledger_hand.flows.uploading import BYTES_PER_MB, UploadNotRead, UploadProblem
from ledger_hand.llm.error_text import hide
from ledger_hand.ports import ModelError, ModelErrorKind, StorageError, StorageErrorKind
from ledger_hand.settings import (
    DATA_DIRECTORY_VARIABLE,
    SERVICES,
    ModelSettings,
    Plug,
    Variable,
    every_key,
    key_variable,
)
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

# The same, said for one plug of one kind; looked up after the status codes. A
# cloud service keeps its own list of models; none of them is installed here.
MODEL_FAILURES_BY_PLUG: Mapping[tuple[ModelErrorKind, Plug], str] = MappingProxyType(
    {
        (ModelErrorKind.MODEL_NOT_FOUND, Plug.CLOUD): (
            "The service at {address} has no model named {model}. Check the name on the "
            "Settings page against the service's own list of models. Nothing was sent to the "
            "local model instead."
        ),
        (ModelErrorKind.MODEL_NOT_FOUND, Plug.DEEPSEEK): (
            "{service} has no model named {model}. Check the name on the Settings page "
            "against {service}'s own list of models. Nothing was sent to the local model "
            "instead."
        ),
    }
)

# What a cloud service's failure means, by kind and status code, then by kind
# alone (``None``); looked up first with the cloud or the deepseek plug.
# {service} is the service's name, {key_variable} where its key is read from.
_NOT_LOCAL = "Nothing was sent to the local model instead."
_BACK_TO_LOCAL = f"{Variable.PLUG.value} to {Plug.LOCAL.value} on the Settings page"
_CLOUD_KEY_REFUSED = (
    "{service} at {address} did not take the key{status}. Check {key_variable} in the "
    "environment, where the key is set, and that it may use {model}; then start the program "
    f"again. {_NOT_LOCAL}"
)
CLOUD_FAILURES: Mapping[tuple[ModelErrorKind, int | None], str] = MappingProxyType(
    {
        (ModelErrorKind.UNREACHABLE, None): (
            "No answer came from {service} at {address}. Check that this machine can reach "
            "the internet and that the address is right on the Settings page, then try "
            f"again. {_NOT_LOCAL}"
        ),
        (ModelErrorKind.TIMED_OUT, None): (
            "No whole reply came from {service} at {address} within {seconds} seconds. Try "
            f"again, or allow more time on the Settings page. {_NOT_LOCAL}"
        ),
        (ModelErrorKind.SERVER_ERROR, 402): (
            "{service} at {address} turned the call down because the account has no money "
            "left on it (status 402). Top it up on the service's own website, or set "
            f"{_BACK_TO_LOCAL} to use the model on this machine. {_NOT_LOCAL}"
        ),
        (ModelErrorKind.SERVER_ERROR, 401): _CLOUD_KEY_REFUSED,
        (ModelErrorKind.SERVER_ERROR, 403): _CLOUD_KEY_REFUSED,
        (ModelErrorKind.SERVER_ERROR, 400): (
            "{service} at {address} turned the request down as it was sent{status}. Check "
            f"the model's name on the Settings page. {_NOT_LOCAL}"
        ),
        (ModelErrorKind.RATE_LIMITED, None): (
            "{service} turned the call away because it was called too often. Wait a little, "
            f"then try again. {_NOT_LOCAL}"
        ),
        # Every server error with no sentence above: 500, 502, 503, a 404 that is not a
        # missing model, 422 and the like, and one with no status at all.
        (ModelErrorKind.SERVER_ERROR, None): (
            "{service} at {address} reported an error of its own{status}. Wait a while, "
            f"then try again. {_NOT_LOCAL}"
        ),
    }
)
# Rate limited by a cloud service that said how long to wait.
_CLOUD_RATE_LIMITED_FOR = (
    "{service} turned the call away because it was called too often, and asked to wait "
    f"{{wait}} seconds. Wait that long, then try again. {_NOT_LOCAL}"
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

# What happened to the book, and what can be done. Nothing is written to a book
# that is refused, unless SQLite first rolled back a write to it that had been
# cut off part way; the book's own message, said after the sentence, then says so.
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
            "The book's file is a database, but not this program's book, so this program "
            f"does not use it. Move that file away, {_ELSEWHERE}."
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


# Why an uploaded screenshot was not read, and what can be done. {size} is the
# file's size and {limit} the limit, both in MB; {model} is the vision model's
# name and {address} where the server is.
_SETTINGS_PAGE = "on the Settings page"
SCREENSHOT_FAILURES: Mapping[UploadProblem, str] = MappingProxyType(
    {
        UploadProblem.CLOUD_PLUG: (
            "A screenshot is read through the local plug only, and "
            f"{Variable.PLUG.value} is {{plug}}, so nothing was sent anywhere. "
            "Typing a trade in the chat works as before; to read a screenshot, set "
            f"{Variable.PLUG.value} to {Plug.LOCAL.value} {_SETTINGS_PAGE}."
        ),
        UploadProblem.TOO_LARGE: (
            "The file is {size} MB, more than the limit of {limit} MB, so nothing was sent. "
            "Take a smaller screenshot, or raise the limit, "
            f"{Variable.SCREENSHOT_MAX_MB.value}, {_SETTINGS_PAGE}."
        ),
        UploadProblem.NOT_A_PICTURE: (
            "The file is neither a PNG nor a JPEG, judged by what it holds rather than by its "
            "name, so nothing was sent. Only PNG and JPEG screenshots are read: save the "
            "screenshot as one of the two and try again, or type the trade in the chat."
        ),
        UploadProblem.VISION_MODEL_MISSING: (
            "The model server at {address} has no model named {model}, so nothing was sent. "
            "That is the vision model, which reads screenshots, not the model that extracts "
            f"the trades. Check its name, {Variable.VISION_NAME.value}, {_SETTINGS_PAGE}, or "
            "install it with Ollama (ollama pull {model})."
        ),
        UploadProblem.VISION_MODEL_UNCHECKED: (
            "The model server could not be asked whether it has the vision model {model}, so "
            "the screenshot was not sent."
        ),
        UploadProblem.MODEL_FAILED: (
            "The vision model {model} gave no usable reply while reading the screenshot, so "
            "nothing was recorded."
        ),
        UploadProblem.EMPTY: (
            "The vision model {model} read nothing off the screenshot, so nothing was "
            "recorded. Check that it is a screenshot of an order, then try again. If it keeps "
            f"coming back empty, raise {Variable.MAX_REPLY_TOKENS.value} {_SETTINGS_PAGE}, or "
            f"set {Variable.THINK.value} to off: a model that thinks first can spend the whole "
            "reply on its thinking."
        ),
        UploadProblem.CUT_OFF: (
            "The vision model {model} reached the longest reply while reading the screenshot, "
            "so what it read was cut off and not used; nothing was recorded. Raise "
            f"{Variable.MAX_REPLY_TOKENS.value} {_SETTINGS_PAGE}, or set {Variable.THINK.value} "
            "to off, then try again."
        ),
    }
)
# The problems a model's failure is said after, when there is one.
_WITH_TROUBLE = frozenset({UploadProblem.VISION_MODEL_UNCHECKED, UploadProblem.MODEL_FAILED})

# Said for the vision model in place of the sentences for status 400 and for a
# reply not in the agreed form, which speak of the reply table and the passage.
VISION_REFUSED = (
    "The model server at {address} turned the request down as it was sent{status}.{said} "
    f"Check {_SETTINGS_PAGE} that {{model}}, named by {Variable.VISION_NAME.value}, is a "
    "model that can see pictures."
)
VISION_MALFORMED = (
    "The model server answered, but not in a form this program can read, so nothing could "
    "be used. Try again; if it keeps failing, look at the server's own log."
)


def screenshot_not_read(outcome: UploadNotRead, settings: ModelSettings) -> str:
    """What is said when an uploaded screenshot was not read: what happened, and what to do.

    ``settings`` are those the parts were built from: the vision model, and
    the address, are theirs.
    """
    said = SCREENSHOT_FAILURES[outcome.problem].format(
        size=_megabytes_up(outcome.size_bytes),
        limit=written(outcome.limit_mb),
        model=settings.vision_model,
        address=settings.base_url,
        plug=settings.plug.value,
    )
    if outcome.problem not in _WITH_TROUBLE or outcome.error is None:
        return said
    if outcome.problem is UploadProblem.VISION_MODEL_UNCHECKED:
        vision = replace(settings, model=settings.vision_model)
        return f"{said} {model_trouble(outcome.error, vision)}"
    return f"{said} {vision_trouble(outcome.error, settings)}"


def vision_trouble(error: ModelError, settings: ModelSettings) -> str:
    """The sentence for the vision model's ``error`` while reading, naming the vision model.

    Looked up as ``model_trouble`` does, but for status 400 and for a reply
    not in the agreed form, which have sentences of their own here.
    """
    vision = replace(settings, model=settings.vision_model)
    if error.kind is ModelErrorKind.MALFORMED_REPLY:
        return _filled(VISION_MALFORMED, vision, error)
    if error.kind is ModelErrorKind.SERVER_ERROR and error.status == 400:
        return _filled(VISION_REFUSED, vision, error)
    return model_trouble(error, vision)


def _megabytes_up(size: int) -> str:
    """``size`` bytes in MB with two decimals, rounded up, so a file over the limit shows over."""
    hundredths = -(-size * 100 // BYTES_PER_MB)
    return f"{hundredths // 100}.{hundredths % 100:02d}"


def model_failed(failure: Failure, settings: ModelSettings) -> str:
    """What is said when a passage ended because the model failed, or its replies were unusable."""
    said = f"The model gave no usable reply while {failure.step.value}, so nothing was recorded."
    if failure.error is None:
        return f"{said} {REPLY_UNREADABLE}"
    return f"{said} {model_trouble(failure.error, settings)}"


def model_trouble(error: ModelError, settings: ModelSettings) -> str:
    """The sentence for ``error``: by its kind and status code if there is one, then by its
    kind and the plug the settings choose, else by its kind.

    A rate-limited call whose server said how long to wait is said with the
    wait, in whole seconds, rounded up.
    """
    template = _template(error.kind, error.status, error.retry_after_seconds, settings.plug)
    return _filled(template, settings, error)


def model_kind_trouble(kind: ModelErrorKind, settings: ModelSettings) -> str:
    """The sentence for a model failure known only by its kind, looked up as ``model_trouble`` does.

    With no status code and no wait, it is the kind's sentence for the plug the
    settings choose, or else the kind's own.
    """
    return _filled(_template(kind, None, None, settings.plug), settings, None)


def _template(
    kind: ModelErrorKind, status: int | None, wait_seconds: float | None, plug: Plug
) -> str:
    """By kind and status, then by kind and plug, then a rate-limited call's wait, then by kind.

    With a cloud plug, ``CLOUD_FAILURES`` comes first, by kind and status, then by kind.
    """
    if plug is not Plug.LOCAL:
        cloud = _cloud_template(kind, status, wait_seconds)
        if cloud is not None:
            return cloud
    template = None
    if status is not None:
        template = MODEL_FAILURES_BY_STATUS.get((kind, status))
    if template is None:
        template = MODEL_FAILURES_BY_PLUG.get((kind, plug))
    if template is None and kind is ModelErrorKind.RATE_LIMITED:
        template = None if wait_seconds is None else RATE_LIMITED_FOR
    if template is None:
        template = MODEL_FAILURES[kind]
    return template


def _cloud_template(
    kind: ModelErrorKind, status: int | None, wait_seconds: float | None
) -> str | None:
    """A cloud service's sentence for the failure, when there is one."""
    if kind is ModelErrorKind.RATE_LIMITED and wait_seconds is not None:
        return _CLOUD_RATE_LIMITED_FOR
    if status is not None and (kind, status) in CLOUD_FAILURES:
        return CLOUD_FAILURES[(kind, status)]
    return CLOUD_FAILURES.get((kind, None))


def _filled(template: str, settings: ModelSettings, error: ModelError | None) -> str:
    """``template`` with the settings' values, and the failure's own when there is one."""
    service = SERVICES.get(settings.plug)
    return template.format(
        service="The service" if service is None else service.name,
        key_variable=key_variable(settings).value,
        address=settings.base_url,
        model=settings.model,
        seconds=written(settings.timeout_seconds),
        status="" if error is None or error.status is None else f" (status {error.status})",
        said="" if error is None else _said(error, settings),
        wait="" if error is None else _wait(error),
    )


def _said(error: ModelError, settings: ModelSettings) -> str:
    """The start of what the server answered, as a sentence; nothing when it sent nothing."""
    if not error.snippet:
        return ""
    shown = error.snippet
    for key in every_key(settings):
        shown = hide(shown, key)
    return f' Its answer began: "{shown}".'


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
