"""Tests of ``scripts/try_assistant.py`` with ``--names-file``: answers kept there, and used.

Without the option no file is read or written; with it, an answer to
"which asset" is kept in the file named, and the next run matches the
name at once. A scripted model stands in for every call; every sentence
is invented, and the file is in a temporary folder.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import copied, screened, table
from tests.flows.test_conversation_asset_pick import RECORD, row_of, said_as


def run(arguments: list[str], answers: list[str] = ()) -> str:  # type: ignore[assignment]
    words = said_as("小可")
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(row_of("小可"))],
        answers=[copied(answer) for answer in answers],
    )
    out = io.StringIO()
    try_assistant.main([*arguments, words, *answers], out=out, model=model, max_steps=6)
    return out.getvalue()


def test_an_answer_is_kept_in_the_file_named_and_matched_the_next_time(tmp_path: Path) -> None:
    place = tmp_path / "names.json"

    first = run(["--names-file", str(place)], ["KO"])
    second = run(["--names-file", str(place)])

    assert "asked about: coin" in first
    assert json.loads(place.read_text(encoding="utf-8"))["demo"][0]["code"] == "KO"
    assert 'Took "小可" as KO (Coca-Cola) from your answer on 2026-11-24.' in second
    assert "asked about" not in second


def test_without_the_option_no_file_is_read_or_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    run([], ["KO"])
    printed = run([])

    assert "asked about: coin" in printed
    assert list(tmp_path.iterdir()) == []


def test_the_option_with_no_path_after_it_is_refused() -> None:
    out = io.StringIO()

    assert try_assistant.main(["--names-file"], out=out) == 2
    assert "--names-file needs the path of a file after it" in out.getvalue()
