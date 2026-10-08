"""Settings: the one place in the package that reads environment variables.

``load_model_settings`` reads the model settings from environment variables
named ``LEDGER_HAND_MODEL_...`` (the ``Variable`` enumeration lists them) and
returns a ``ModelSettings``. A variable that is not set, or is set to nothing
but blanks, takes its default. A value that is not in the expected form, or
is out of range, is refused with a ``SettingsError`` that names the variable;
so is a variable that has the prefix but is not one of the known names,
because a misspelt name would otherwise be ignored without a word.

The key, if there is one, is kept in a ``Secret``: printing it, or printing
the settings, shows a placeholder, and no error message here ever repeats it.

Every default is a named constant below, with the reason for its value. Tests
compare against these names, never against the numbers, so a default is
tuned here and nowhere else.

This module only reads and checks settings. It does not talk to the model,
store anything or know about the other parts of the package.

Names defined here: ``ENV_PREFIX``, ``Variable``, the ``DEFAULT_...``
constants, ``MAX_RETRIES``, ``Secret``, ``SettingsError``, ``ModelSettings``,
``load_model_settings``.
"""

from __future__ import annotations

import enum
import math
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

ENV_PREFIX = "LEDGER_HAND_MODEL_"


class Variable(enum.Enum):
    """The environment variables this module reads."""

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


# Ollama's own address on this machine: the model runs locally by default.
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
# The model the project was built and measured with.
DEFAULT_MODEL = "qwen2.5:7b"
# Extraction has to give the same answer to the same text, so the model
# always takes its likeliest word.
DEFAULT_TEMPERATURE = 0.0
# Keeps every word in play, so the temperature alone says how adventurous the
# model is. At temperature 0 it changes nothing.
DEFAULT_TOP_P = 1.0
# Room for a JSON list of about ten trades. A reply that reaches it is marked
# as cut off rather than passed on as if it were whole.
DEFAULT_MAX_REPLY_TOKENS = 1024
# Ollama's own default (2048 or 4096, depending on the version) is too short
# for a prompt with examples and a schema, and Ollama drops the start of a
# prompt that does not fit, without an error. qwen2.5:7b reads up to 32768;
# a longer window costs memory. Measured with qwen2.5:7b: the first prompt
# with its examples is about 1,750 tokens, and Chinese text about 0.7 tokens
# a character (English about 0.3). So the longest passage the ledger keeps,
# 16,384 characters of Chinese, comes to about 11,600 tokens; with the prompt
# and a full reply that is about 14,400, which leaves some 2,000 to spare.
DEFAULT_CONTEXT_TOKENS = 16384
# Leaves room for loading the model into memory on the first call (a cold
# start takes seconds to tens of seconds) and then writing a full-length reply.
DEFAULT_TIMEOUT_SECONDS = 120.0
# Retries after the first try, for the failures that may pass on their own
# (timed out, rate limited, server error): three tries in all.
DEFAULT_RETRIES = 2
# The wait before the first retry; each later wait is twice the one before.
DEFAULT_RETRY_WAIT_SECONDS = 1.0
# The most retries a setting may ask for, so that the waits stay finite.
MAX_RETRIES = 10
# Wording a follow-up question is the one call where some variety reads more
# naturally than the same sentence every time. What is asked, and every fact
# the question may use, are fixed by the program before the model writes,
# and a sentence that strays is replaced by the program's own; so a higher
# temperature changes only the wording. Judging a passage, extraction and
# reading an answer keep the temperature above, which is 0 by default.
DEFAULT_QUESTION_TEMPERATURE = 0.7

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
    """Where the model is, which one, its key, and the defaults for calling it.

    ``retries`` is how many times a call that may pass on its own is tried
    again; ``retry_wait_seconds`` is the wait before the first retry, and each
    later wait is twice the one before. ``question_temperature`` is the
    temperature for wording a follow-up question; every other call uses
    ``temperature``.
    """

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


def load_model_settings(environ: Mapping[str, str] | None = None) -> ModelSettings:
    """The model settings from ``environ``, or from the process's environment when ``None``."""
    source = os.environ if environ is None else environ
    _refuse_unknown_variables(source)
    given = {variable: _given(source, variable) for variable in Variable}
    key = given[Variable.KEY]
    return ModelSettings(
        base_url=_or(given[Variable.URL], DEFAULT_BASE_URL, _strip_trailing_slash),
        model=_or(given[Variable.NAME], DEFAULT_MODEL, str),
        api_key=None if key is None else Secret(key),
        temperature=_or(
            given[Variable.TEMPERATURE], DEFAULT_TEMPERATURE, _number(Variable.TEMPERATURE)
        ),
        top_p=_or(given[Variable.TOP_P], DEFAULT_TOP_P, _number(Variable.TOP_P)),
        max_reply_tokens=_or(
            given[Variable.MAX_REPLY_TOKENS],
            DEFAULT_MAX_REPLY_TOKENS,
            _whole(Variable.MAX_REPLY_TOKENS),
        ),
        context_tokens=_or(
            given[Variable.CONTEXT_TOKENS], DEFAULT_CONTEXT_TOKENS, _whole(Variable.CONTEXT_TOKENS)
        ),
        timeout_seconds=_or(
            given[Variable.TIMEOUT_SECONDS],
            DEFAULT_TIMEOUT_SECONDS,
            _number(Variable.TIMEOUT_SECONDS),
        ),
        retries=_or(given[Variable.RETRIES], DEFAULT_RETRIES, _whole(Variable.RETRIES)),
        retry_wait_seconds=_or(
            given[Variable.RETRY_WAIT_SECONDS],
            DEFAULT_RETRY_WAIT_SECONDS,
            _number(Variable.RETRY_WAIT_SECONDS),
        ),
        question_temperature=_or(
            given[Variable.QUESTION_TEMPERATURE],
            DEFAULT_QUESTION_TEMPERATURE,
            _number(Variable.QUESTION_TEMPERATURE),
        ),
    )


def _refuse_unknown_variables(source: Mapping[str, str]) -> None:
    known = {variable.value for variable in Variable}
    unknown = sorted(name for name in source if name.startswith(ENV_PREFIX) and name not in known)
    if unknown:
        listed = ", ".join(sorted(known))
        raise SettingsError(f"unknown setting {', '.join(unknown)}; the known ones are {listed}")


def _given(source: Mapping[str, str], variable: Variable) -> str | None:
    """The variable's value without surrounding blanks; ``None`` when unset or blank."""
    value = source.get(variable.value)
    if value is None or not value.strip():
        return None
    return value.strip()


def _or[T](text: str | None, default: T, convert: Callable[[str], T]) -> T:
    return default if text is None else convert(text)


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
