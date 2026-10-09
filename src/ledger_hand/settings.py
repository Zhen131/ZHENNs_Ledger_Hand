"""Settings: the one place in the package that reads environment variables.

``load_model_settings`` reads the model settings from environment variables
named ``LEDGER_HAND_MODEL_...`` (the ``Variable`` enumeration lists them) and
returns a ``ModelSettings``. One of them chooses the plug that talks to the
model (``Plug``): the local Ollama by default, or a cloud service. A
variable that is not set, or is set to nothing but blanks, takes its
default. A value that is not in the expected form, or is out of range, is
refused with a ``SettingsError`` that names the variable; so is a variable
that has the prefix but is not one of the known names, because a misspelt
name would otherwise be ignored without a word.

The key, if there is one, is kept in a ``Secret``: printing it, or printing
the settings, shows a placeholder, and no error message here ever repeats it.

``apply_changes`` puts changes made on the interface's settings page into
settings already read: each value is read and checked exactly as the same
variable is read from the environment, a blank value takes the default, and
the key cannot be changed that way. Nothing is written back to the
environment or anywhere else, so a change lasts only as long as whoever
holds the settings it returns.

``load_data_places`` reads where the program keeps its data: the folder
named by ``LEDGER_HAND_DATA_DIR``, or ``data`` in the current working
directory when it is not set. The book (the SQLite file of saved trades) and
the folder of export files are inside it. This variable does not start with
the model settings' prefix, so it is not one of them, and the other
``LEDGER_HAND_`` variables the scripts read are left alone as before. Reading
it makes nothing: the folders are made by whatever first writes there.

Every default is a named constant below. Tests compare against these
names, never against the numbers, so a default is tuned here and nowhere
else. What each variable sets and the reason for its default are kept as
data, in ``ABOUT``, and only there: the settings page and the README's table
of settings show them as written there.

This module only reads and checks settings, each variable on its own. It
does not talk to the model, store anything or know about the other parts of
the package. Whether the settings fit together for the plug they choose (a
cloud service needs an address of its own, and off this machine https and a
key) is checked where the plug is built, not here: so setting one variable
alone never makes reading the settings fail because of another.

Names defined here: ``ENV_PREFIX``, ``Variable``, ``Plug``, the ``DEFAULT_...``
constants, ``MAX_RETRIES``, ``Secret``, ``SettingsError``, ``ModelSettings``,
``About``, ``ABOUT``, ``load_model_settings``, ``apply_changes``,
``DATA_DIRECTORY_VARIABLE``, ``BOOK_FILE_NAME``, ``EXPORTS_DIRECTORY_NAME``,
``DataPlaces`` and ``load_data_places``.
"""

from __future__ import annotations

import enum
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

ENV_PREFIX = "LEDGER_HAND_MODEL_"


class Variable(enum.Enum):
    """The environment variables this module reads."""

    PLUG = ENV_PREFIX + "PLUG"
    URL = ENV_PREFIX + "URL"
    NAME = ENV_PREFIX + "NAME"
    KEY = ENV_PREFIX + "KEY"
    TEMPERATURE = ENV_PREFIX + "TEMPERATURE"
    TOP_P = ENV_PREFIX + "TOP_P"
    MAX_REPLY_TOKENS = ENV_PREFIX + "MAX_REPLY_TOKENS"
    CONTEXT_TOKENS = ENV_PREFIX + "CONTEXT_TOKENS"
    TIMEOUT_SECONDS = ENV_PREFIX + "TIMEOUT_SECONDS"
    RETRIES = ENV_PREFIX + "RETRIES"
    RETRY_WAIT_SECONDS = ENV_PREFIX + "RETRY_WAIT_SECONDS"
    QUESTION_TEMPERATURE = ENV_PREFIX + "QUESTION_TEMPERATURE"


class Plug(enum.StrEnum):
    """Which plug talks to the model; the values are what the variable is set to."""

    LOCAL = "local"
    """Ollama's own chat endpoint, on this machine by default."""
    CLOUD = "cloud"
    """The OpenAI-style chat endpoint most cloud services offer."""


# The defaults. The reason for each is in ``ABOUT`` below, and only there.
DEFAULT_PLUG = Plug.LOCAL
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TOP_P = 1.0
DEFAULT_MAX_REPLY_TOKENS = 1024
DEFAULT_CONTEXT_TOKENS = 16384
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_RETRIES = 2
DEFAULT_RETRY_WAIT_SECONDS = 1.0
DEFAULT_QUESTION_TEMPERATURE = 0.7
# The most retries a setting may ask for, so that the waits stay finite.
MAX_RETRIES = 10

_WHOLE_NUMBER = re.compile(r"[0-9]{1,9}")
_PLAIN_NUMBER = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,9})?")
# Printable ASCII without spaces: what an address, a model name or a key may hold.
_VISIBLE_ASCII = re.compile(r"[!-~]{1,2048}")


class Secret:
    """A value that must never be shown. Printing it shows a placeholder."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """The value itself, for the one place that has to send it."""
        return self._value

    def __repr__(self) -> str:
        return "Secret('<hidden>')"

    def __str__(self) -> str:
        return "<hidden>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and other._value == self._value

    def __hash__(self) -> int:
        return hash((Secret, self._value))


class SettingsError(ValueError):
    """A setting is missing its form or out of range; the message names the variable."""


@dataclass(frozen=True, kw_only=True)
class ModelSettings:
    """Which plug, where the model is, which one, its key, and the defaults for calling it.

    ``retries`` is how many times a call that may pass on its own is tried
    again; ``retry_wait_seconds`` is the wait before the first retry, and each
    later wait is twice the one before. ``question_temperature`` is the
    temperature for wording a follow-up question; every other call uses
    ``temperature``.
    """

    plug: Plug = DEFAULT_PLUG
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: Secret | None = None
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    max_reply_tokens: int = DEFAULT_MAX_REPLY_TOKENS
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES
    retry_wait_seconds: float = DEFAULT_RETRY_WAIT_SECONDS
    question_temperature: float = DEFAULT_QUESTION_TEMPERATURE

    def __post_init__(self) -> None:
        if not isinstance(self.plug, Plug):
            raise SettingsError(
                f"{Variable.PLUG.value}: the plug must be a Plug, one of {_plugs()}"
            )
        _check_base_url(self.base_url)
        _check_visible(Variable.NAME, self.model)
        if self.api_key is not None and not isinstance(self.api_key, Secret):
            raise SettingsError(f"{Variable.KEY.value}: the key must be kept in a Secret")
        if self.api_key is not None:
            _check_key(self.api_key)
        _check_range(Variable.TEMPERATURE, self.temperature, lambda value: value >= 0, "0 or more")
        _check_range(Variable.TOP_P, self.top_p, lambda value: 0 < value <= 1, "above 0, at most 1")
        _check_whole(Variable.MAX_REPLY_TOKENS, self.max_reply_tokens, lowest=1)
        _check_whole(Variable.CONTEXT_TOKENS, self.context_tokens, lowest=1)
        _check_range(
            Variable.TIMEOUT_SECONDS, self.timeout_seconds, lambda value: value > 0, "above 0"
        )
        _check_whole(Variable.RETRIES, self.retries, lowest=0, highest=MAX_RETRIES)
        _check_range(
            Variable.RETRY_WAIT_SECONDS,
            self.retry_wait_seconds,
            lambda value: value >= 0,
            "0 or more",
        )
        _check_range(
            Variable.QUESTION_TEMPERATURE,
            self.question_temperature,
            lambda value: value >= 0,
            "0 or more",
        )


@dataclass(frozen=True)
class About:
    """One variable: the ``ModelSettings`` field it sets, what it sets, and why its default."""

    field: str
    sets: str
    reason: str


ABOUT: Mapping[Variable, About] = MappingProxyType(
    {
        Variable.PLUG: About(
            "plug",
            "Which plug talks to the model: local, Ollama's own chat endpoint; or cloud, the "
            "OpenAI-style chat endpoint most cloud services offer. The cloud plug needs the "
            "service's address, and for an address off this machine https and a key.",
            "Local, so that by default the model runs on this machine and nothing that is "
            "typed leaves it. Setting an address or a key never switches to a cloud service; "
            "only this does.",
        ),
        Variable.URL: About(
            "base_url",
            "Where the model server is: an http or https address, with no user name, "
            "password, query or fragment.",
            "Ollama's own address on this machine, so by default the model runs locally "
            "and nothing that is typed leaves the machine.",
        ),
        Variable.NAME: About(
            "model",
            "Which model to ask.",
            "The model the program was built and measured with.",
        ),
        Variable.KEY: About(
            "api_key",
            "A key, sent as a bearer token, for a server that needs one. Never shown, "
            "and set in the environment only.",
            "None: the local Ollama needs no key.",
        ),
        Variable.TEMPERATURE: About(
            "temperature",
            "How adventurous the model is when it judges a passage, extracts the trades "
            "and reads an answer. 0 or more.",
            "Extraction has to give the same answer to the same text, so the model "
            "always takes its likeliest word.",
        ),
        Variable.TOP_P: About(
            "top_p",
            "Keeps only the likeliest words whose chances add up to this. Above 0, at most 1.",
            "Keeps every word in play, so the temperature alone says how adventurous the "
            "model is; at temperature 0 it changes nothing.",
        ),
        Variable.MAX_REPLY_TOKENS: About(
            "max_reply_tokens",
            "The longest reply, in tokens, the pieces of words a model counts in. "
            "A whole number, 1 or more.",
            "Room for a JSON list of about ten trades. A reply that reaches it is marked "
            "as cut off rather than passed on as if it were whole.",
        ),
        Variable.CONTEXT_TOKENS: About(
            "context_tokens",
            "How much the model reads at once, in tokens. A whole number, 1 or more.",
            "Ollama's own default (2048 or 4096, depending on the version) is too short "
            "for a prompt with examples and a schema, and Ollama drops the start of a "
            "prompt that does not fit, without an error. Measured with qwen2.5:7b, which "
            "reads up to 32768: the first prompt with its examples is about 1,750 tokens, "
            "and the longest passage the ledger keeps, 16,384 characters of Chinese, about "
            "11,600 (English text takes fewer). With a full reply that is about 14,400, "
            "which leaves some 2,000 to spare; a longer window costs memory.",
        ),
        Variable.TIMEOUT_SECONDS: About(
            "timeout_seconds",
            "How long to wait for the whole reply, in seconds. Above 0. Not sent to the model.",
            "Leaves room for loading the model into memory on the first call (a cold start "
            "takes seconds to tens of seconds) and then writing a full-length reply.",
        ),
        Variable.RETRIES: About(
            "retries",
            "How many times a call that timed out, was rate limited or met a server error "
            "is tried again; a request the server turned down as wrong, with a status from "
            f"400 to 499 other than 429, is not. 0 to {MAX_RETRIES}.",
            "Three tries in all, for the failures that may pass on their own, without "
            "keeping the person waiting for long.",
        ),
        Variable.RETRY_WAIT_SECONDS: About(
            "retry_wait_seconds",
            "The wait before the first retry, in seconds; each later wait is twice the one "
            "before. A server that says how long to wait is waited for that long instead, up "
            "to a minute. 0 or more.",
            "A second gives a busy server a moment to recover, and with each wait twice "
            "the one before, two retries add three seconds at most when the server does not "
            "say how long to wait.",
        ),
        Variable.QUESTION_TEMPERATURE: About(
            "question_temperature",
            "The temperature for wording a follow-up question. 0 or more.",
            "Wording a follow-up question is the one call where some variety reads more "
            "naturally than the same sentence every time. What is asked, and every fact "
            "the question may use, are fixed by the program before the model writes, and "
            "a sentence that strays is replaced by the program's own, so a higher "
            "temperature changes only the wording. Judging a passage, extraction and "
            f"reading an answer keep {Variable.TEMPERATURE.value}, 0 by default.",
        ),
    }
)


def load_model_settings(environ: Mapping[str, str] | None = None) -> ModelSettings:
    """The model settings from ``environ``, or from the process's environment when ``None``."""
    source = os.environ if environ is None else environ
    _refuse_unknown_variables(source)
    given = {variable: _given(source, variable) for variable in Variable}
    return ModelSettings(
        **{
            ABOUT[variable].field: _read(variable, text)
            for variable, text in given.items()
            if text is not None
        }
    )


def apply_changes(settings: ModelSettings, changes: Mapping[Variable, str]) -> ModelSettings:
    """``settings`` with ``changes`` put in, each read and checked as the environment's would be.

    A value of nothing but blanks takes the variable's default, as an empty
    environment variable does. The key cannot be changed this way. A value
    in the wrong form or out of range raises ``SettingsError``, naming the
    variable and its rule; ``settings`` itself never changes.
    """
    if not isinstance(settings, ModelSettings):
        raise TypeError(f"settings must be ModelSettings, not {type(settings).__name__}")
    values: dict[str, object] = {}
    for variable, text in changes.items():
        if not isinstance(variable, Variable):
            raise SettingsError(f"unknown setting {variable!r}; the known ones are {_known()}")
        if variable is Variable.KEY:
            raise SettingsError(
                f"{Variable.KEY.value}: the key is set in the environment only; "
                "it cannot be changed here"
            )
        if not isinstance(text, str):
            raise SettingsError(f"{variable.value}: a value is text, not {type(text).__name__}")
        field = ABOUT[variable].field
        given = text.strip()
        values[field] = getattr(_DEFAULTS, field) if not given else _read(variable, given)
    return replace(settings, **values)


def _known() -> str:
    return ", ".join(sorted(variable.value for variable in Variable))


def _read(variable: Variable, text: str) -> object:
    """``text``, already stripped and not empty, read as ``variable``'s value; not yet checked."""
    if variable is Variable.PLUG:
        return _plug(text)
    if variable is Variable.URL:
        return _strip_trailing_slash(text)
    if variable is Variable.NAME:
        return text
    if variable is Variable.KEY:
        return Secret(text)
    if variable in _WHOLE_VARIABLES:
        return _whole(variable)(text)
    return _number(variable)(text)


_WHOLE_VARIABLES = frozenset({Variable.MAX_REPLY_TOKENS, Variable.CONTEXT_TOKENS, Variable.RETRIES})


def _refuse_unknown_variables(source: Mapping[str, str]) -> None:
    known = {variable.value for variable in Variable}
    unknown = sorted(name for name in source if name.startswith(ENV_PREFIX) and name not in known)
    if unknown:
        raise SettingsError(f"unknown setting {', '.join(unknown)}; the known ones are {_known()}")


def _given(source: Mapping[str, str], variable: Variable) -> str | None:
    """The variable's value without surrounding blanks; ``None`` when unset or blank."""
    value = source.get(variable.value)
    if value is None or not value.strip():
        return None
    return value.strip()


def _plugs() -> str:
    return " or ".join(plug.value for plug in Plug)


def _plug(text: str) -> Plug:
    try:
        return Plug(text)
    except ValueError:
        raise SettingsError(
            f"{Variable.PLUG.value}: {_shown(text)} is not a plug; it is {_plugs()}"
        ) from None


def _strip_trailing_slash(text: str) -> str:
    return text.rstrip("/") if text.rstrip("/") else text


def _number(variable: Variable) -> Callable[[str], float]:
    def convert(text: str) -> float:
        if _PLAIN_NUMBER.fullmatch(text) is None:
            raise SettingsError(
                f"{variable.value}: {_shown(text)} is not a plain number such as 0.5 "
                "(digits, at most one point, no sign or exponent)"
            )
        return float(text)

    return convert


def _whole(variable: Variable) -> Callable[[str], int]:
    def convert(text: str) -> int:
        if _WHOLE_NUMBER.fullmatch(text) is None:
            raise SettingsError(
                f"{variable.value}: {_shown(text)} is not a whole number of at most 9 digits"
            )
        return int(text)

    return convert


def _shown(text: str) -> str:
    """A value, quoted and shortened, for an error message. Never used for the key."""
    return repr(text if len(text) <= 40 else text[:40] + "...")


def _check_base_url(url: object) -> None:
    name = Variable.URL.value
    if not isinstance(url, str) or _VISIBLE_ASCII.fullmatch(url) is None:
        raise SettingsError(f"{name}: an address is printable ASCII without spaces")
    not_an_address = SettingsError(
        f"{name}: {_shown(url)} is not an address such as {DEFAULT_BASE_URL}"
    )
    try:
        parts = urlsplit(url)
    except ValueError:
        raise not_an_address from None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise not_an_address
    try:
        port_is_valid = parts.port is None or parts.port > 0
    except ValueError:
        port_is_valid = False
    if not port_is_valid:
        raise SettingsError(f"{name}: {_shown(url)} has a port that is not a valid number")
    if parts.username is not None or parts.password is not None:
        raise SettingsError(
            f"{name}: an address may not hold a user name or password; use {Variable.KEY.value}"
        )
    if parts.query or parts.fragment or url.endswith(("?", "#")):
        raise SettingsError(f"{name}: an address may not have a query or a fragment")


def _check_visible(variable: Variable, value: object) -> None:
    if not isinstance(value, str) or _VISIBLE_ASCII.fullmatch(value) is None:
        raise SettingsError(f"{variable.value}: {value!r} is not printable ASCII without spaces")


def _check_key(key: Secret) -> None:
    # Says what is wrong without ever repeating the key.
    value = key.reveal()
    if not isinstance(value, str) or _VISIBLE_ASCII.fullmatch(value) is None:
        raise SettingsError(
            f"{Variable.KEY.value}: a key is printable ASCII without spaces; this one is not"
        )


def _check_range(
    variable: Variable, value: object, keeps: Callable[[float], bool], expected: str
) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SettingsError(f"{variable.value}: must be a number, not {type(value).__name__}")
    if not math.isfinite(value) or not keeps(value):
        raise SettingsError(f"{variable.value}: {value!r} is out of range; it must be {expected}")


def _check_whole(
    variable: Variable, value: object, *, lowest: int, highest: int | None = None
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"{variable.value}: must be a whole number, not {type(value).__name__}")
    if value < lowest or (highest is not None and value > highest):
        top = "" if highest is None else f" and at most {highest}"
        raise SettingsError(
            f"{variable.value}: {value} is out of range; it must be {lowest} or more{top}"
        )


# What a blank value on the settings page stands for, as a blank variable does.
# Made last, once every check it runs is defined.
_DEFAULTS = ModelSettings()


# --- where the data is kept --------------------------------------------------

DATA_DIRECTORY_VARIABLE = "LEDGER_HAND_DATA_DIR"
# Beside the program, where the repository's own ignore file keeps it out of Git.
DEFAULT_DATA_DIRECTORY = "data"
# The book: the SQLite file of saved trades.
BOOK_FILE_NAME = "ledger-hand-book.sqlite3"
# The folder export files are written into.
EXPORTS_DIRECTORY_NAME = "exports"


@dataclass(frozen=True)
class DataPlaces:
    """Where the data is kept: the folder, the book inside it, and the folder of exports."""

    directory: Path

    @property
    def book(self) -> Path:
        return self.directory / BOOK_FILE_NAME

    @property
    def exports(self) -> Path:
        return self.directory / EXPORTS_DIRECTORY_NAME


def load_data_places(
    environ: Mapping[str, str] | None = None, *, working_directory: Path | None = None
) -> DataPlaces:
    """Where the data is kept, from ``environ`` or the process's environment when ``None``.

    A relative folder, and the default, are taken from ``working_directory``,
    or the current one when ``None``; a leading ``~`` is the home folder.
    Nothing is made here.
    """
    source = os.environ if environ is None else environ
    base = Path.cwd() if working_directory is None else working_directory
    value = source.get(DATA_DIRECTORY_VARIABLE)
    if value is None or not value.strip():
        return DataPlaces(base / DEFAULT_DATA_DIRECTORY)
    named = value.strip()
    if "\0" in named:
        raise SettingsError(
            f"{DATA_DIRECTORY_VARIABLE}: a folder's name cannot hold a NUL character"
        )
    return DataPlaces(base / Path(named).expanduser())
