"""Tests of the judged run's two switches: tidying each sentence first, and the voice set.

Without ``--tidy`` a run hands each sentence to the flow exactly as written,
and writes what a run wrote before the switch was added: the lines below
were taken from the earlier code, run with the same scripted model on the
same five sentences, and only the parts that change at every run are
blanked. A scripted model stands in; every reply is invented.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest

import evals.judged_run as judged_run
from evals.gold import Sentence, Split
from evals.run import Backend
from ledger_hand.core.spoken_text import tidy_spoken
from ledger_hand.flows.progress import Progress
from tests.extraction.scripted_runs import row, table
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import screened

# The parts of a results file that differ at every run, whatever the code:
# the first line's commit, whether the tree was clean, the model's
# fingerprint, the server's version and the moment the run started; each
# sentence's time taken; and the moment in the file's name.
CHANGING_IN_HEAD = ("commit", "worktree_clean", "model_fingerprint", "server_version", "started_at")
CHANGING_IN_SENTENCE = ("seconds",)

_LINES_BEFORE = {
    "debug": (
        "debug.json",
        "4529d98323ad1df4d38f5a5b73cdf1082b6a1cd08a0604a454ecf7986104f4d8",
        ("d01", 0),
        ("d02", 1),
        ("d03", 0),
        ("d04", 1),
        ("d05", 0),
    ),
    "final": (
        "final.json",
        "34afdeb36b787d7e62a6a1a0149838c2dfde8c186a1bb89ea6b3de1205090406",
        ("f01", 0),
        ("f02", 1),
        ("f03", 0),
        ("f04", 1),
        ("f05", 0),
    ),
}


def _before(split: str) -> list[dict[str, object]]:
    """The lines the earlier code wrote for ``split``, the changing parts blanked."""
    set_name, sha, *sentences = _LINES_BEFORE[split]
    lines: list[dict[str, object]] = [
        {
            "record": "run",
            "set_file": f"evals/sets/{set_name}",
            "set_sha256": sha,
            "screen_prompt": "screen-2",
            "extraction_prompt": "first-3",
            "asset_table": "built-in: the coin table's coins, priced in USDT",
            "commit": None,
            "worktree_clean": None,
            "model": "scripted",
            "model_fingerprint": None,
            "server_version": None,
            "parameters": {},
            "started_at": None,
            "hold_other_unit": True,
        }
    ]
    for sentence_id, wrong in sentences:
        lines.append(
            {
                "record": "sentence",
                "id": sentence_id,
                "stage": "a question is waiting for its answer",
                "drafts": 1,
                "gold_trades": 1,
                "whole_right": 0,
                "silent_wrong": wrong,
                "seconds": None,
                "draft_reminders": [[]],
                "passage_reminders": ["NUMBERS_LEFT_OVER"],
                "draft_whole_right": [False],
                "held": [],
            }
        )
    lines.append(
        {
            "record": "end",
            "sentences": 5,
            "gold_trades": 5,
            "whole_right": 0,
            "silent_wrong": 2,
            "gold_trades_judged_away": 0,
        }
    )
    return lines


def _backend() -> Backend:
    model = RoutedModel(
        screen=[screened(("spot_trade", "x"))] * 5,
        extraction=[table(row(side="buy", coin="BTC", quantity="0.05", price="6.2万"))] * 5,
    )
    return Backend(
        model=model,
        name="scripted",
        fingerprint="f",
        server_version="v",
        base_url="http://127.0.0.1:1",
        parameters={},
    )


class _Run:
    """Runs of ``main`` with the scripted model on five sentences, into the test's folder."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
        self.passages: list[str] = []
        self.sentences: list[Sentence] = []
        whole = judged_run.load_set
        started = judged_run.start

        def five(path: Path, split: Split) -> list[Sentence]:
            self.sentences = list(whole(path, split))[:5]
            return self.sentences

        def start(passage: str, *args: object, **options: object) -> Progress:
            self.passages.append(passage)
            return started(passage, *args, **options)  # type: ignore[arg-type]

        monkeypatch.setattr(judged_run, "local_backend", lambda name: _backend())
        monkeypatch.setattr(judged_run, "load_set", five)
        monkeypatch.setattr(judged_run, "start", start)
        monkeypatch.setattr(judged_run, "TOOL_RESULTS_DIR", folder)

    def __call__(self, *switches: str) -> tuple[int, str, list[dict[str, object]]]:
        out = io.StringIO()
        base = ["--screen", "screen-2", "--extract", "first-3", "--hold-other-unit"]
        code = judged_run.main([*base, *switches], out=out)
        if code != 0:
            return code, out.getvalue(), []
        path = Path(out.getvalue().splitlines()[0].removeprefix("results: "))
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        return code, path.name, lines


def _blanked(lines: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    blanked = []
    for line in lines:
        changing = CHANGING_IN_HEAD if line["record"] == "run" else CHANGING_IN_SENTENCE
        blanked.append({key: None if key in changing else value for key, value in line.items()})
    return blanked


@pytest.mark.parametrize(("switches", "split"), [((), "debug"), (("--final-exam",), "final")])
def test_without_tidy_a_run_writes_what_it_wrote_before(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, switches: tuple[str, ...], split: str
) -> None:
    run = _Run(monkeypatch, tmp_path)

    code, name, lines = run(*switches)

    assert code == 0
    assert run.passages == [sentence.text for sentence in run.sentences]
    assert _blanked(lines) == _before(split)
    assert "tidy" not in lines[0]
    assert re.fullmatch(
        rf"judged-[0-9]{{8}}T[0-9]{{6}}Z-{split}-screen-2-first-3-hold\.jsonl", name
    )


def test_with_tidy_the_flow_is_handed_each_sentence_tidied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _Run(monkeypatch, tmp_path)

    code, name, lines = run("--tidy")

    assert code == 0
    assert run.passages == [
        tidy_spoken(sentence.text, sentence.zone).text for sentence in run.sentences
    ]
    assert lines[0]["tidy"] is True
    assert re.fullmatch("[0-9a-f]{64}", str(lines[0]["tidy_module_sha256"]))
    assert name.endswith("-debug-screen-2-first-3-hold-tidy.jsonl")
    for sentence, line in zip(run.sentences, lines[1:-1], strict=True):
        kinds = {change.kind.name for change in tidy_spoken(sentence.text, sentence.zone).changes}
        assert line["tidied"] == sorted(kinds)


def test_the_voice_set_can_be_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run = _Run(monkeypatch, tmp_path)

    code, name, lines = run("--voice", "--tidy")

    assert code == 0
    assert lines[0]["set_file"] == "evals/sets/voice.json"
    assert name.endswith("-voice-screen-2-first-3-hold-tidy.jsonl")


def test_the_voice_and_the_final_set_cannot_both_be_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _Run(monkeypatch, tmp_path)

    code, said, _lines = run("--voice", "--final-exam")

    assert code == 2
    assert "cannot start" in said
    assert list(tmp_path.iterdir()) == []
