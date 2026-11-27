"""Tests of the measure of the program's own matching of names: what it writes for each half.

The locked half's results file holds the conditions and the counts alone,
never a sentence, and its name holds "hidden", so the hidden-run log's own
check covers it. The practice half, measured directly, writes a line for
each sentence. No model is called; the files go into a temporary folder.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evals.name_set import Half, NameSentence, load_name_set
from evals.name_table_run import direct_assets, results_name, run

HEAD: dict[str, object] = {
    "record": "run",
    "way": "direct",
    "started_at": datetime(2026, 11, 27, 12, 0, tzinfo=UTC).isoformat(),
}


def nothing(sentence: NameSentence) -> tuple[set[str], dict[str, object], bool]:
    return set(), {"came": "nothing"}, False


def test_the_locked_halfs_file_holds_no_sentence_and_its_name_says_hidden(
    tmp_path: Path,
) -> None:
    path, lines, end = run({**HEAD, "half": "locked"}, nothing, Half.LOCKED, folder=tmp_path)

    written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [one["record"] for one in written] == ["run", "end"]
    assert "hidden" in path.name and path.name == results_name(HEAD, Half.LOCKED)
    assert written[1] == end
    assert lines and all(line["record"] == "sentence" for line in lines)
    text = path.read_text(encoding="utf-8")
    assert all(line["id"] not in text and line["said"] not in text for line in lines)


def test_the_practice_half_measured_directly_writes_each_sentence(tmp_path: Path) -> None:
    path, lines, end = run(
        {**HEAD, "half": "practice"}, direct_assets, Half.PRACTICE, folder=tmp_path
    )

    written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    practice = [one for one in load_name_set().sentences if one.half is Half.PRACTICE]
    assert len(written) == len(practice) + 2
    assert "hidden" not in path.name
    assert end["record"] == "end"
    assert all("table_gives" in line for line in lines)
