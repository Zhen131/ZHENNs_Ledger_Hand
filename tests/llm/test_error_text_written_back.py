"""Tests of hiding a key that a server writes back in another form than it was sent.

A key may hold any printable character but a space, quotes and backslashes
among them. A server may repeat it inside a JSON string (once or twice
over), as ``\\uXXXX`` escapes, with ``\\/`` for a slash, percent-encoded in
either case, or HTML-escaped with named or numbered entities. Each form must
be hidden wherever it stands, in a snippet and in a detail as well, and the
text around it must stay. Every key below is invented.
"""

from __future__ import annotations

import html
import json
import urllib.parse

import pytest

from ledger_hand.llm.error_text import HIDDEN, detail, hide, snippet
from ledger_hand.settings import Secret

# Every character a JSON string, an address or an HTML page writes another way.
VALUE = "sk-invented-\"quote\\back/slash&amp<lt>gt%pc'apos"
KEY = Secret(VALUE)


def json_string(text: str) -> str:
    """``text`` as it stands inside a JSON string, without the quotes around it."""
    return json.dumps(text)[1:-1]


FORMS = {
    "as sent": VALUE,
    "json": json_string(VALUE),
    "json in json": json_string(json_string(VALUE)),
    "json, ascii only": json.dumps(VALUE, ensure_ascii=True)[1:-1],
    "json with escaped slashes": json_string(VALUE).replace("/", "\\/"),
    "every character as \\u, lower case": "".join(f"\\u{ord(c):04x}" for c in VALUE),
    "every character as \\u, upper case": "".join(f"\\u{ord(c):04X}" for c in VALUE),
    "percent-encoded": urllib.parse.quote(VALUE, safe=""),
    "percent-encoded, lower case": urllib.parse.quote(VALUE, safe="").lower(),
    "percent-encoded for a form": urllib.parse.quote_plus(VALUE),
    "percent-encoded but the safe ones": urllib.parse.quote(VALUE),
    "html": html.escape(VALUE),
    "html, quotes left": html.escape(VALUE, quote=False),
    "html, numbered": "".join(f"&#{ord(c)};" for c in VALUE),
    "html, numbered in hexadecimal": "".join(f"&#x{ord(c):X};" for c in VALUE),
}


@pytest.mark.parametrize("form", list(FORMS))
def test_each_form_of_the_key_is_hidden_and_the_text_around_it_stays(form: str) -> None:
    written = FORMS[form]

    hidden = hide(f"before {written} after", KEY)

    assert hidden == f"before {HIDDEN} after"


@pytest.mark.parametrize("form", list(FORMS))
def test_each_form_is_hidden_in_a_snippet_and_a_detail(form: str) -> None:
    written = FORMS[form]
    body = f'{{"error": {{"message": "Incorrect API key provided: {written}"}}}}'

    shown = [snippet(body.encode("utf-8"), KEY) or "", detail(body, KEY)]

    for text in shown:
        assert written not in text
        assert VALUE not in text
        assert HIDDEN in text


def test_every_form_at_once_in_one_text_is_hidden() -> None:
    text = " | ".join(FORMS.values())

    hidden = hide(text, KEY)

    assert hidden == " | ".join([HIDDEN] * len(FORMS))


def test_forms_mixed_within_the_key_are_hidden_too() -> None:
    # The first half as sent, the second half escaped as JSON.
    middle = len(VALUE) // 2
    mixed = VALUE[:middle] + json_string(VALUE[middle:])

    assert hide(mixed, KEY) == HIDDEN


def test_a_text_without_the_key_is_left_as_it_is() -> None:
    text = 'sk-invented-"quote and %22 and &quot; but never the whole key'

    assert hide(text, KEY) == text


def test_a_plain_key_is_hidden_as_before() -> None:
    plain = Secret("sk-invented-abcdef0123456789")

    assert hide("Bearer sk-invented-abcdef0123456789.", plain) == f"Bearer {HIDDEN}."
