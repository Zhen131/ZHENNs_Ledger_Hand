"""Tests of the script's ``--help``: alone, it prints the script's description and reads nothing.

Given as the only argument, ``--help`` or ``-h`` prints how to give a
passage, that standard input is read when there are no arguments, and what
the exit statuses mean, and ends with status 0. Nothing else is read: not
standard input, not the settings, not the machine's zone, and no model is
called. Given with other words, ``--help`` is part of the passage, as any
word is. Every passage below is invented.
"""

from __future__ import annotations

import io

import pytest

from scripts import try_extraction
from tests.extraction.scripted_runs import NOW, ZONE
from tests.fakes.scripted_model import ScriptedModel


class Untouched:
    """Stands for what must not be read; records every time it is."""

    def __init__(self) -> None:
        self.reads: list[str] = []

    def read_input(self) -> str:
        self.reads.append("standard input")
        return ""

    def model(self, out: io.StringIO) -> None:
        self.reads.append("settings, to build the model")

    def settings(self) -> None:
        self.reads.append("settings")

    def machine_zone(self) -> None:
        self.reads.append("machine's zone")


@pytest.mark.parametrize("asking", ["--help", "-h"])
def test_help_alone_prints_the_usage_and_reads_nothing(
    asking: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    untouched = Untouched()
    monkeypatch.setattr(try_extraction, "_model", untouched.model)
    monkeypatch.setattr(try_extraction, "_machine_zone", untouched.machine_zone)
    monkeypatch.setattr(try_extraction, "load_model_settings", untouched.settings)
    out = io.StringIO()

    status = try_extraction.main([asking], read_input=untouched.read_input, out=out)

    shown = out.getvalue()
    assert status == 0
    assert untouched.reads == []
    for expected in ["scripts/try_extraction.py", "standard input", "Exit status", "--help"]:
        assert expected in shown, expected


@pytest.mark.parametrize("words", [["--help", "me"], ["-h", "买了", "1", "BTC"], ["买了", "-h"]])
def test_help_with_other_words_is_part_of_the_passage(words: list[str]) -> None:
    model = ScriptedModel(['{"trades": []}'])
    out = io.StringIO()

    status = try_extraction.main(
        words, read_input=lambda: "", out=out, model=model, now=NOW, zone=ZONE
    )

    assert status == 0
    assert model.calls[0].messages[-1].content == " ".join(words)
    assert "Exit status" not in out.getvalue()
