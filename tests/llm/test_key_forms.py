"""Tests of finding a key written back in a known way, by the passes that never go back.

The key here holds characters that are themselves the start of an escape
(``%41``, ``&``, a backslash before a letter), so a pass that read too much
or too little would miss it. Each form must be found whole, with the text
around it left as it is; a key mixing the characters as they are with one
pass's escapes is found too; and a key of nothing but backslashes is looked
for only as it was sent. Every key is invented.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse

import pytest

from ledger_hand.llm.key_forms import WAYS, key_spans

KEY = "sk-inv\"ent\\QZXJ7%41&<b>/'end~"


def json_string(text: str) -> str:
    return json.dumps(text)[1:-1]


FORMS = {
    "as sent": KEY,
    "json": json_string(KEY),
    "json with escaped slashes": json_string(KEY).replace("/", "\\/"),
    "json in json": json_string(json_string(KEY)),
    "json in json in json": json_string(json_string(json_string(KEY))),
    "percent-encoded": urllib.parse.quote(KEY, safe=""),
    "percent-encoded, lower case": re.sub(
        "%[0-9A-F]{2}", lambda escape: escape.group().lower(), urllib.parse.quote(KEY, safe="")
    ),
    "percent-encoded for a form": urllib.parse.quote_plus(KEY),
    "html": html.escape(KEY),
    "html, numbered": "".join(f"&#{ord(c)};" for c in KEY),
    "html, numbered in hexadecimal": "".join(f"&#x{ord(c):x};" for c in KEY),
    "html, numbered in upper-case hexadecimal": "".join(f"&#X{ord(c):X};" for c in KEY),
    "every character as \\u": "".join(f"\\u{ord(c):04x}" for c in KEY),
    "every character as \\U, upper case": "".join(f"\\U{ord(c):04X}" for c in KEY),
}


@pytest.mark.parametrize("form", list(FORMS))
def test_each_form_is_found_whole_and_nothing_around_it(form: str) -> None:
    text = f"before {FORMS[form]} after"

    assert key_spans(text, KEY) == [(len("before "), len(text) - len(" after"))]


def test_a_key_mixing_characters_as_they_are_with_one_ways_escapes_is_found() -> None:
    middle = len(KEY) // 2
    for written in (
        KEY[:middle] + urllib.parse.quote(KEY[middle:], safe=""),
        KEY[:middle] + html.escape(KEY[middle:]),
        KEY[:middle] + "".join(f"\\u{ord(c):04x}" for c in KEY[middle:]),
    ):
        assert key_spans(f"[{written}]", KEY) == [(1, 1 + len(written))]


def test_two_places_are_both_found_and_kept_apart() -> None:
    text = f"{KEY} and {json_string(KEY)}"

    assert key_spans(text, KEY) == [(0, len(KEY)), (len(KEY) + 5, len(text))]


def test_a_key_of_backslashes_only_is_looked_for_only_as_it_was_sent() -> None:
    assert key_spans("a \\\\\\ b \\\\ c", "\\\\\\") == [(2, 5)]


def test_nothing_is_found_in_a_text_without_the_key() -> None:
    text = "%41 &amp; \\u0041 \\\\ sk-inv ent QZXJ7"

    assert key_spans(text, KEY) == []
    assert key_spans(text, "") == []


def test_the_ways_are_these_four() -> None:
    assert [way.name for way in WAYS] == ["escaped", "json", "percent", "html"]
