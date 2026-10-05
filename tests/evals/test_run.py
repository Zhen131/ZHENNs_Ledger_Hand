"""Tests of the experiment runner and the summary, with the scripted model standing in.

Only sentences of the debug set are run here, and only through the scripted
model. The final set is never run in a test: that it is chosen only by the
final-exam switch is checked without running it.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from evals import run as runner
from evals import summarize as summarizer
from evals.gold import DEBUG_SET, FINAL_SET, Split
from evals.records import read_results, score_to_json
from evals.scoring import ResultKind
from evals.tables import markdown, rescore, summarize
from ledger_hand.ports import ModelError, ModelErrorKind
from tests.extraction.scripted_runs import row, table
from tests.fakes.scripted_model import ScriptedModel, Step

D01 = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.05 个 BTC",
        price="63,480",
        fee="1.6 USDT",
        time="昨晚 8 点 15 分",
        platform="币安",
        opinion="这个位置我觉得不亏",
    )
)
NOTHING = table()
SHA256 = re.compile(r"[0-9a-f]{64}")


def backend(*steps: Step, fingerprint: str = "a" * 64) -> runner.Backend:
    return runner.Backend(
        model=ScriptedModel(steps),
        name="scripted",
        fingerprint=fingerprint,
        server_version="0.0.0",
        base_url="http://127.0.0.1:59999",
        parameters={"temperature": 0.0, "asks_again": 1},
    )


def run(
    arguments: list[str], chosen: runner.Backend, results_dir: Path
) -> tuple[int, str, Path | None]:
    out = io.StringIO()
    status = runner.main(arguments, out=out, backend=lambda _: chosen, results_dir=results_dir)
    files = sorted(results_dir.glob("*.jsonl"))
    return status, out.getvalue(), files[-1] if files else None


def lines_of(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_the_first_line_records_the_conditions_of_the_run(tmp_path: Path) -> None:
    status, _, path = run(["--only", "d01", "d24"], backend(D01, NOTHING), tmp_path)

    assert status == 0
    assert path is not None and path.name.endswith("-debug-first.jsonl")
    head = lines_of(path)[0]
    assert head["record"] == "run"
    assert (head["set"], head["final_exam_switch"], head["prompt"]) == ("debug", False, "first")
    assert head["set_file"] == "evals/sets/debug.json"
    assert SHA256.fullmatch(str(head["set_sha256"]))
    files = head["prompt_files"]
    assert isinstance(files, list)
    assert [f["path"] for f in files] == [
        "src/ledger_hand/extraction/prompts/first.py",
        "src/ledger_hand/extraction/prompts/first_examples.py",
    ]
    assert all(SHA256.fullmatch(f["sha256"]) for f in files)
    assert SHA256.fullmatch(str(head["prompt_content_sha256"]))
    assert re.fullmatch(r"[0-9a-f]{40}", str(head["commit"]))
    assert isinstance(head["worktree_clean"], bool)
    assert (head["model"], head["model_fingerprint"]) == ("scripted", "a" * 64)
    assert head["server_version"] == "0.0.0"
    assert head["parameters"] == {"temperature": 0.0, "asks_again": 1}
    assert head["only"] == ["d01", "d24"]
    assert "started_at" in head


def test_each_sentence_has_a_line_and_the_run_an_end(tmp_path: Path) -> None:
    _, shown, path = run(["--only", "d01", "d24"], backend(D01, NOTHING), tmp_path)

    assert path is not None
    _, first, second, end = lines_of(path)
    copied = {k: v for k, v in json.loads(D01)["trades"][0].items() if v and k != "side"}
    assert (first["id"], second["id"]) == ("d01", "d24")
    assert first["result"] == "extracted"
    assert first["replies"] == [D01]
    assert len(first["drafts"]) == 1  # type: ignore[arg-type]
    assert first["copied"] == [copied]
    assert first["scores"]["whole_right"] == 1  # type: ignore[index]
    assert len(first["calls"]) == 1  # type: ignore[arg-type]
    assert isinstance(first["seconds"], float)
    assert second["drafts"] == []
    assert end["record"] == "end"
    assert "whole right" in shown and "Scores by group" in shown


def test_nothing_in_a_results_file_names_a_place_on_this_machine(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d24"], backend(NOTHING), tmp_path)

    assert path is not None
    assert str(Path.home()) not in path.read_text(encoding="utf-8")


def test_the_summary_is_saved_beside_the_results_and_matches_a_fresh_one(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d01", "d24"], backend(D01, NOTHING), tmp_path)
    assert path is not None

    saved = json.loads(summarizer.summary_path(path).read_text(encoding="utf-8"))
    out = io.StringIO()

    assert saved == json.loads(json.dumps(summarize(read_results(path)), ensure_ascii=False))
    assert summarizer.main([str(path), "--check"], out=out) == 0
    groups = saved["groups"]
    assert groups["all scored sentences"]["whole_right"] == 1
    assert groups["no trade (talk)"]["no_trade_right"] == 1


def test_the_scores_written_during_the_run_are_those_worked_out_again(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d01", "d24"], backend(D01, NOTHING), tmp_path)
    assert path is not None
    results = read_results(path)

    for line, (_, _, score) in zip(results.sentences, rescore(results), strict=True):
        assert line["scores"] == score_to_json(score)


def test_a_changed_summary_is_caught(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d24"], backend(NOTHING), tmp_path)
    assert path is not None
    summary_file = summarizer.summary_path(path)
    data = json.loads(summary_file.read_text(encoding="utf-8"))
    data["groups"]["all scored sentences"]["whole_right"] = 99
    summary_file.write_text(json.dumps(data), encoding="utf-8")

    assert summarizer.main([str(path), "--check"], out=io.StringIO()) == 1


class RunCutShortError(Exception):
    """Stands for a run cut short."""


class StopAfterOne:
    """A model that answers once and then stops the run."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, *_arguments: object, **_keywords: object) -> object:
        self.calls += 1
        if self.calls > 1:
            raise RunCutShortError
        return ScriptedModel([D01]).chat([])


def test_a_run_cut_short_is_carried_on_where_it_stopped(tmp_path: Path) -> None:
    cut = backend()
    cut = runner.Backend(**{**cut.__dict__, "model": StopAfterOne()})
    with pytest.raises(RunCutShortError):
        run(["--only", "d01", "d24"], cut, tmp_path)
    (path,) = tmp_path.glob("*.jsonl")
    with path.open("ab") as stream:
        stream.write(b'{"record": "sentence", "id": "d2')

    status, _, _ = run(["--only", "d01", "d24", "--resume", str(path)], backend(NOTHING), tmp_path)

    assert status == 0
    records = lines_of(path)
    assert [line["record"] for line in records] == ["run", "sentence", "sentence", "end"]
    assert [line.get("id") for line in records[1:3]] == ["d01", "d24"]


def test_a_run_is_not_carried_on_under_other_conditions(tmp_path: Path) -> None:
    cut = runner.Backend(**{**backend().__dict__, "model": StopAfterOne()})
    with pytest.raises(RunCutShortError):
        run(["--only", "d01", "d24"], cut, tmp_path)
    (path,) = tmp_path.glob("*.jsonl")

    other = backend(NOTHING, fingerprint="b" * 64)
    status, shown, _ = run(["--only", "d01", "d24", "--resume", str(path)], other, tmp_path)

    assert status == 2
    assert "model_fingerprint" in shown


def test_a_finished_run_is_not_carried_on(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d24"], backend(NOTHING), tmp_path)

    status, shown, _ = run(["--only", "d24", "--resume", str(path)], backend(), tmp_path)

    assert status == 2
    assert "already finished" in shown


def test_a_failed_model_and_an_unreadable_reply_are_recorded(tmp_path: Path) -> None:
    timed_out = ModelError(ModelErrorKind.TIMED_OUT, "no reply in time")
    chosen = backend(timed_out, "not json", "still not json")

    status, _, path = run(["--only", "d01", "d02"], chosen, tmp_path)

    assert status == 0 and path is not None
    _, first, second, _ = lines_of(path)
    assert first["result"] == ResultKind.MODEL_FAILED.value
    assert first["failure"]["kind"] == "timed_out"  # type: ignore[index]
    assert second["result"] == ResultKind.REPLY_UNREADABLE.value
    assert second["failure"] == {"reply_problems": ["NOT_JSON", "NOT_JSON"]}
    assert second["replies"] == ["not json", "still not json"]
    assert second["scores"]["missed"] == 1  # type: ignore[index]


def test_a_passage_not_to_record_has_what_the_check_says(tmp_path: Path) -> None:
    futures = table(row(side="buy", coin="BTC", price="62,800", time="昨天"))

    _, _, path = run(["--only", "d27"], backend(futures), tmp_path)

    assert path is not None
    line = lines_of(path)[1]
    assert line["group"] == "not_to_record"
    assert line["checks"] == ["ONE_MORE_OF_QUANTITY_PRICE_TOTAL FEE"]
    summary = summarize(read_results(path))
    assert summary["not_to_record"][0]["drafts"] == 1  # type: ignore[index]
    assert summary["groups"]["all scored sentences"]["sentences"] == 0  # type: ignore[index]


def test_the_debug_set_is_the_default_and_the_final_set_needs_its_switch() -> None:
    assert runner.set_for(runner._arguments([])) == (Split.DEBUG, DEBUG_SET)
    assert runner.set_for(runner._arguments(["--prompt", "first"])) == (Split.DEBUG, DEBUG_SET)
    assert runner.set_for(runner._arguments(["--final-exam"])) == (Split.FINAL, FINAL_SET)


def test_an_id_of_the_final_set_is_refused_without_the_switch(tmp_path: Path) -> None:
    status, shown, path = run(["--only", "f01"], backend(), tmp_path)

    assert status == 2
    assert "not in the debug set" in shown
    assert path is None


def test_a_backend_that_cannot_start_stops_the_run(tmp_path: Path) -> None:
    def broken(_: str | None) -> runner.Backend:
        raise ModelError(ModelErrorKind.UNREACHABLE, "nothing answers")

    out = io.StringIO()
    status = runner.main(["--only", "d01"], out=out, backend=broken, results_dir=tmp_path)

    assert status == 2
    assert "unreachable" in out.getvalue()
    assert not list(tmp_path.iterdir())


def test_the_recording_model_keeps_the_replies() -> None:
    recorder = runner.RecordingModel(ScriptedModel(["one", "two"]))

    recorder.chat([])
    recorder.chat([])

    assert [reply.text for reply in recorder.replies] == ["one", "two"]


def test_the_tables_hold_every_section(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d01", "d24", "d27"], backend(D01, NOTHING, NOTHING), tmp_path)
    assert path is not None

    text = markdown(summarize(read_results(path)))

    for heading in (
        "Scores by group",
        "Each field",
        "by kind",
        "Wrong values in drafts with no issue about them (0)",
        "Half copies",
        "Passages not to record",
        "Every scored sentence",
    ):
        assert heading in text
    assert "| all scored sentences | 2 | 2 / 2 (100.0%) | 1 / 1 (100.0%) |" in text
