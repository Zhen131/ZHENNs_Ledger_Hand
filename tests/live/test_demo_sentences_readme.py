"""The README's sentences for a demo are the file's, word for word. Needs no model.

Not marked ``live_model``, so the quick tier runs it. ``README.md`` lists
the sentences under "Sentences for a demo", each as a numbered line with the
sentence in a code span, and under it a line that starts with "Gets:" and
says what it gets. ``tests/live/demo_sentences.json`` holds the same
sentences, with what the live check holds each to and the words the README
writes under it. The test reads the section and checks that it lists
exactly the file's sentences, in the file's order, each with the file's
words under it, so the two cannot part ways.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
SENTENCES_FILE = Path(__file__).with_name("demo_sentences.json")
HEADING = "## Sentences for a demo"
ITEM = re.compile(r"^(\d+)\. `(?P<said>[^`]+)`$")
GETS = "   Gets: "


def section() -> list[str]:
    lines = README.read_text(encoding="utf-8").splitlines()
    assert lines.count(HEADING) == 1, f"the README has no single {HEADING!r}"
    start = lines.index(HEADING) + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return lines[start:end]


def listed() -> list[tuple[str, str]]:
    """Each sentence the section lists, with the words under it."""
    lines = section()
    found = []
    for number, line in enumerate(lines):
        match = ITEM.match(line)
        if match is None:
            continue
        under = lines[number + 1] if number + 1 < len(lines) else ""
        assert under.startswith(GETS), f"no 'Gets:' line under {line!r}"
        found.append((match["said"], under[len(GETS) :]))
    return found


def in_the_file() -> list[tuple[str, str]]:
    sentences = json.loads(SENTENCES_FILE.read_text(encoding="utf-8"))["sentences"]
    return [(sentence["said"], sentence["shows"]) for sentence in sentences]


def test_the_readme_lists_the_files_sentences_word_for_word_in_order() -> None:
    assert [said for said, _ in listed()] == [said for said, _ in in_the_file()]


def test_under_each_sentence_the_readme_says_what_the_file_says_it_gets() -> None:
    assert listed() == in_the_file()


def test_the_items_are_numbered_from_one_without_a_gap() -> None:
    numbers = [int(match[1]) for line in section() if (match := ITEM.match(line))]
    assert numbers == list(range(1, len(in_the_file()) + 1))


def test_the_file_holds_between_eight_and_ten_sentences_of_every_kind() -> None:
    sentences = json.loads(SENTENCES_FILE.read_text(encoding="utf-8"))["sentences"]
    kinds = [sentence["kind"] for sentence in sentences]
    assert 8 <= len(sentences) <= 10
    assert kinds.count("record") + kinds.count("held_back") >= 3
    assert kinds.count("held_back") <= 1
    assert kinds.count("ask") >= 3
    assert kinds.count("change") >= 2
    assert len({sentence["id"] for sentence in sentences}) == len(sentences)
