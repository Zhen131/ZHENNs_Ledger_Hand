"""Reading what a model server sent back as JSON, and the fields every chat reply shares.

``read_json_object`` gives the body of an answer as a JSON object, or
raises ``MALFORMED_REPLY`` saying why it is not one (the body could not be
read, is not UTF-8 text, is not JSON, or is JSON but not an object).
``json_object_or_none`` gives the same object, or ``None`` where the other
raises: it is for looking into the body of an answer that has already
failed, without failing a second time. NaN and Infinity are refused by
both, though Python's reader takes them by default: they are not JSON.

``count``, ``model_name`` and ``is_valid_unicode`` read a token count, the
answering model's name and the text of a reply the same way for every plug:
a count is a whole number, 0 or more; a name is printable text of at most
``MAX_MODEL_NAME`` characters, else the name asked for; text holding a lone
surrogate, which JSON can carry but UTF-8 cannot, is not valid.

Names defined here: ``MAX_MODEL_NAME``, ``read_json_object``,
``json_object_or_none``, ``count``, ``model_name``, ``is_valid_unicode``.
"""

from __future__ import annotations

import json

from ledger_hand.llm.exchange import Answer, Endpoint, malformed

MAX_MODEL_NAME = 256


def read_json_object(answer: Answer, endpoint: Endpoint) -> dict[str, object]:
    """The body as a JSON object, or ``MALFORMED_REPLY`` saying why it is not one."""
    if answer.body_problem is not None:
        raise malformed(answer.body_problem, answer, endpoint)
    try:
        text = answer.body.decode("utf-8")
    except UnicodeDecodeError:
        raise malformed("is not UTF-8 text", answer, endpoint) from None
    try:
        data = json.loads(text, parse_constant=_refuse_constant)
    except (ValueError, RecursionError):
        raise malformed("is not JSON", answer, endpoint) from None
    if not isinstance(data, dict):
        raise malformed("is not a JSON object", answer, endpoint)
    return data


def json_object_or_none(answer: Answer) -> dict[str, object] | None:
    """The body as a JSON object, or ``None`` when it is not one."""
    if answer.body_problem is not None:
        return None
    try:
        data = json.loads(answer.body.decode("utf-8"), parse_constant=_refuse_constant)
    except (ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


def count(value: object) -> int | None:
    """A token count as the server gave it; ``None`` when it is not a whole number, 0 or more."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def model_name(value: object, requested_model: str) -> str:
    """The answering model's name as the server gave it, if it is a fit one; else the one asked."""
    if isinstance(value, str) and value.isprintable() and 0 < len(value) <= MAX_MODEL_NAME:
        return value
    return requested_model


def is_valid_unicode(text: str) -> bool:
    """False for text holding a lone surrogate, which JSON can carry but UTF-8 cannot."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _refuse_constant(name: str) -> object:
    # NaN and Infinity are not JSON, though Python's reader takes them by default.
    raise ValueError(f"{name} is not JSON")
