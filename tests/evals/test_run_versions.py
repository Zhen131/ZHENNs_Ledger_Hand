"""Tests of the runner with every prompt version: the files each lists, and its table's fingerprint.

The run line records the files a version's words are written in; a version
built on the first prompt lists the first prompt's files as well, so the
fingerprints cover every word it sends. The fingerprint of the reply table
is recorded apart from the prompt's content fingerprint, whose way of being
worked out is unchanged. Only the scripted model is used, and only on the
debug set.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from evals import run as runner
from evals.records import read_results
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.stepwise import STEPWISE_TABLE
from ledger_hand.extraction.reply_table import REPLY_TABLE
from tests.extraction.scripted_runs import table
from tests.fakes.scripted_model import ScriptedModel

PROMPT_DIR = "src/ledger_hand/extraction/prompts/"
FILES = {
    "first": ["first.py", "first_examples.py"],
    "zero_shot": ["zero_shot.py", "first.py"],
    "persona": ["persona.py", "first.py", "first_examples.py"],
    "stepwise": ["stepwise.py", "first.py", "first_examples.py"],
    "price_total": ["price_total.py", "first.py", "first_examples.py"],
}
# The content fingerprint of the first prompt as the baseline run recorded it.
FIRST_CONTENT_SHA256 = "7a510f4aaf16f7830ea5df2ec2071a276006565014e61bf295aa44a57a297112"


def head_of(prompt: str, tmp_path: Path) -> dict[str, object]:
    chosen = runner.Backend(
        model=ScriptedModel([table()]),
        name="scripted",
        fingerprint="a" * 64,
        server_version="0.0.0",
        base_url="http://127.0.0.1:59999",
        parameters={"temperature": 0.0, "asks_again": 1},
    )
    out = io.StringIO()
    status = runner.main(
        ["--only", "d24", "--prompt", prompt],
        out=out,
        backend=lambda _: chosen,
        results_dir=tmp_path,
    )
    assert status == 0, out.getvalue()
    (path,) = tmp_path.glob(f"*-debug-{prompt}.jsonl")
    return dict(read_results(path).run)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_every_version_can_be_named() -> None:
    assert set(runner.PROMPTS) == set(FILES)
    for name, (version, _) in runner.PROMPTS.items():
        assert version.name == name


@pytest.mark.parametrize("prompt", sorted(FILES))
def test_the_run_line_lists_every_file_the_version_is_written_in(
    prompt: str, tmp_path: Path
) -> None:
    head = head_of(prompt, tmp_path)

    files = head["prompt_files"]
    assert isinstance(files, list)
    assert [entry["path"] for entry in files] == [PROMPT_DIR + name for name in FILES[prompt]]
    assert head["prompt"] == prompt


@pytest.mark.parametrize("prompt", sorted(FILES))
def test_the_run_line_records_the_fingerprint_of_the_versions_table(
    prompt: str, tmp_path: Path
) -> None:
    head = head_of(prompt, tmp_path)
    version, _ = runner.PROMPTS[prompt]

    expected = sha256(json.dumps(version.reply_table, ensure_ascii=False))
    assert head["reply_table_sha256"] == expected


def test_only_stepwise_sends_another_table(tmp_path: Path) -> None:
    tables = {
        name: json.dumps(version.reply_table, ensure_ascii=False)
        for name, (version, _) in runner.PROMPTS.items()
    }

    assert tables["stepwise"] == json.dumps(STEPWISE_TABLE, ensure_ascii=False)
    assert {name for name, text in tables.items() if text != json.dumps(REPLY_TABLE)} == {
        "stepwise"
    }


def test_the_first_prompts_content_fingerprint_is_the_baselines(tmp_path: Path) -> None:
    head = head_of("first", tmp_path)

    assert head["prompt_content_sha256"] == FIRST_CONTENT_SHA256
    assert runner.PROMPTS["first"][0] is FIRST_PROMPT


def test_a_run_is_not_carried_on_with_another_reply_table(tmp_path: Path) -> None:
    head = head_of("first", tmp_path)

    assert "reply_table_sha256" in runner._SAME_TO_RESUME
    assert head["reply_table_sha256"] == sha256(json.dumps(REPLY_TABLE, ensure_ascii=False))
