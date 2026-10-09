"""Run an experiment: every sentence of a set through extraction, each result saved as it comes.

    .venv/bin/python -m evals.run                      # the debug set, the first prompt
    .venv/bin/python -m evals.run --prompt first --model qwen2.5:7b
    .venv/bin/python -m evals.run --set writings --prompt stepwise
    .venv/bin/python -m evals.run --resume evals/results/<file>.jsonl

Run from the top of the repository. The model is the one the settings name
(see "Model settings" in the README), unless ``--model`` names another; the
parameters (temperature and the rest) are the settings' too. The set is the
debug set, unless ``--set`` names the writings set (``writings``), which is
scored apart. The final set is run only with ``--final-exam``, and the
results file then says so: it is kept for the last run of an experiment.

For each sentence, extraction is given the sentence's own fixed moment and
zone, never the clock. The moment a sentence is done, its line is added to
the results file and written to disk, so a run cut short shows how far it
got; ``--resume`` carries it on from there, under the same conditions only.
When every sentence is done, an ``end`` line is added, the summary is worked
out afresh from the file (``tables``), saved beside it as
``<name>.summary.json`` and printed as tables.

The first line of the results file records the conditions of the run: the
set file and its fingerprint (SHA-256), the prompt version, its files and
their fingerprints, the fingerprint of the reply table it sends, the commit
of the repository and whether the work tree was clean, the model, its
fingerprint and the Ollama version (asked through the local plug's
``ask_identity``), every parameter, and the moment the run began. Paths
are written relative to the repository.

Exit status: 0 the run finished; 2 it could not start (a wrong argument, a
setting, or the model server could not say who it is).

Names defined here: ``main``, ``Backend``, ``RecordingModel``,
``PROMPTS``, ``RESULTS_DIR`` and ``run_sentences``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import TextIO

from evals.gold import DEBUG_SET, FINAL_SET, Group, Sentence, Split, load_set, trade_to_json
from evals.records import (
    LineKind,
    append_line,
    copied_to_json,
    draft_to_json,
    issue_to_json,
    read_results,
    score_to_json,
)
from evals.scoring import Produced, ResultKind, score_sentence
from evals.summarize import summary_path
from evals.tables import markdown, summarize
from evals.writings import WRITINGS_SET
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.trade import TradeRecord
from ledger_hand.core.validation import check_draft
from ledger_hand.extraction.extractor import (
    DEFAULT_ASKS_AGAIN,
    Extracted,
    Extraction,
    ModelFailed,
    PassageRefused,
    ReplyUnreadable,
    extract,
)
from ledger_hand.extraction.prompting import PromptVersion, example_reply
from ledger_hand.extraction.prompts import (
    first,
    first_examples,
    persona,
    price_total,
    stepwise,
    zero_shot,
)
from ledger_hand.extraction.reply_parser import ReplyRows, read_reply
from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import (
    JsonSchema,
    Message,
    ModelError,
    ModelParameters,
    ModelPort,
    ModelReply,
)
from ledger_hand.settings import ModelSettings, SettingsError, load_model_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "evals" / "results"

# The prompt versions an experiment can name, each with the files its words are
# written in: a version built on the first prompt lists the first prompt's files too.
PROMPTS: Mapping[str, tuple[PromptVersion, tuple[ModuleType, ...]]] = {
    "first": (first.FIRST_PROMPT, (first, first_examples)),
    "zero_shot": (zero_shot.ZERO_SHOT_PROMPT, (zero_shot, first)),
    "persona": (persona.PERSONA_PROMPT, (persona, first, first_examples)),
    "stepwise": (stepwise.STEPWISE_PROMPT, (stepwise, first, first_examples)),
    "price_total": (price_total.PRICE_TOTAL_PROMPT, (price_total, first, first_examples)),
}
# The conditions that must be the same for a run to be carried on.
_SAME_TO_RESUME = (
    "set",
    "set_sha256",
    "prompt",
    "prompt_content_sha256",
    "reply_table_sha256",
    "commit",
    "model",
    "model_fingerprint",
    "server_version",
    "parameters",
)


class RecordingModel:
    """A model port that passes every call on and keeps the replies of the current passage."""

    def __init__(self, inner: ModelPort) -> None:
        self._inner = inner
        self.replies: list[ModelReply] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        reply = self._inner.chat(messages, reply_schema=reply_schema, parameters=parameters)
        self.replies.append(reply)
        return reply


@dataclass(frozen=True)
class Backend:
    """The model to ask, who it is, and the parameters it was built with."""

    model: ModelPort
    name: str
    fingerprint: str
    server_version: str
    base_url: str
    parameters: Mapping[str, object]


def _parameters(settings: ModelSettings) -> dict[str, object]:
    return {
        "temperature": settings.temperature,
        "top_p": settings.top_p,
        "max_reply_tokens": settings.max_reply_tokens,
        "context_tokens": settings.context_tokens,
        "timeout_seconds": settings.timeout_seconds,
        "retries": settings.retries,
        "retry_wait_seconds": settings.retry_wait_seconds,
        "asks_again": DEFAULT_ASKS_AGAIN,
    }


def local_backend(model_name: str | None) -> Backend:
    """The model the settings name (or ``model_name``), asked who it is first."""
    settings = load_model_settings()
    if model_name:
        settings = replace(settings, model=model_name)
    identity = ask_identity(settings)
    return Backend(
        model=connect_local_model(settings),
        name=identity.model,
        fingerprint=identity.fingerprint,
        server_version=identity.server_version,
        base_url=settings.base_url,
        parameters=_parameters(settings),
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative(path: Path) -> str:
    """``path`` relative to the repository; only its name when it lies outside."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _prompt_content(prompt: PromptVersion) -> str:
    examples = [[e.passage, example_reply(e)] for e in prompt.examples]
    return json.dumps([prompt.instructions, examples, prompt.ask_again], ensure_ascii=False)


def _reply_table(prompt: PromptVersion) -> str:
    return json.dumps(prompt.reply_table, ensure_ascii=False)


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *arguments],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def _worktree_clean() -> bool:
    results = _relative(RESULTS_DIR)
    return not _git("status", "--porcelain", "--", ".", f":(exclude){results}")


def run_conditions(
    split: Split, set_file: Path, prompt_name: str, backend: Backend, started: datetime
) -> dict[str, object]:
    """The first line of a results file: everything the run's numbers depend on."""
    prompt, modules = PROMPTS[prompt_name]
    files = [Path(str(module.__file__)) for module in modules]
    return {
        "record": LineKind.RUN.value,
        "set": split.value,
        "final_exam_switch": split is Split.FINAL,
        "set_file": _relative(set_file),
        "set_sha256": _sha256(set_file.read_bytes()),
        "prompt": prompt_name,
        "prompt_files": [{"path": _relative(f), "sha256": _sha256(f.read_bytes())} for f in files],
        "prompt_content_sha256": _sha256(_prompt_content(prompt).encode("utf-8")),
        "reply_table_sha256": _sha256(_reply_table(prompt).encode("utf-8")),
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": _worktree_clean(),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "base_url": backend.base_url,
        "parameters": dict(backend.parameters),
        "coin_table": "built-in",
        "started_at": started.isoformat(timespec="seconds"),
    }


def _produced(result: Extraction, replies: Sequence[ModelReply]) -> Produced:
    if isinstance(result, Extracted):
        read = read_reply(replies[-1])
        rows = read.rows if isinstance(read, ReplyRows) else ()
        copied = tuple(row.cells for row in rows if not row.is_empty)
        return Produced(ResultKind.EXTRACTED, result.drafts, result.issues, copied)
    if isinstance(result, ReplyUnreadable):
        return Produced(ResultKind.REPLY_UNREADABLE)
    if isinstance(result, ModelFailed):
        return Produced(ResultKind.MODEL_FAILED)
    return Produced(ResultKind.PASSAGE_REFUSED)


def _failure(result: Extraction) -> dict[str, object] | None:
    if isinstance(result, ModelFailed):
        return {"kind": result.error.kind.value, "message": str(result.error)}
    if isinstance(result, ReplyUnreadable):
        return {"reply_problems": [problem.name for problem in result.problems]}
    if isinstance(result, PassageRefused):
        return {"passage_problem": result.problem.name}
    return None


def _checks(sentence: Sentence, produced: Produced) -> list[str]:
    said: list[str] = []
    for draft in produced.drafts:
        result = check_draft(draft, BUILT_IN_TABLE, sentence.now)
        if isinstance(result, TradeRecord):
            said.append("passes")
        else:
            said.append(" ".join(item.name for item in (*result.missing, *result.violations)))
    return said


def sentence_line(
    sentence: Sentence, result: Extraction, replies: Sequence[ModelReply], seconds: float
) -> dict[str, object]:
    """The results-file line of one sentence."""
    produced = _produced(result, replies)
    calls = [] if isinstance(result, PassageRefused) else list(result.calls)
    line: dict[str, object] = {
        "record": LineKind.SENTENCE.value,
        "id": sentence.id,
        "text": sentence.text,
        "now": sentence.now.isoformat(),
        "zone": sentence.zone,
        "language": sentence.language.value,
        "group": sentence.group.value,
        "kind": None if sentence.kind is None else sentence.kind.value,
        "features": sorted(feature.value for feature in sentence.features),
        "gold": [trade_to_json(trade) for trade in sentence.trades],
        "result": produced.kind.value,
        "failure": _failure(result),
        "replies": [reply.text for reply in replies],
        "calls": [
            {
                "model": call.model,
                "elapsed_seconds": round(call.elapsed_seconds, 3),
                "prompt_tokens": call.prompt_tokens,
                "reply_tokens": call.reply_tokens,
                "finish": call.finish.value,
            }
            for call in calls
        ],
        "drafts": [draft_to_json(draft) for draft in produced.drafts],
        "copied": copied_to_json(produced.copied),
        "issues": [issue_to_json(issue) for issue in produced.issues],
        "seconds": round(seconds, 3),
        "scores": score_to_json(score_sentence(sentence, produced)),
    }
    if sentence.group is Group.NOT_TO_RECORD:
        line["checks"] = _checks(sentence, produced)
    return line


def run_sentences(
    sentences: Sequence[Sentence],
    backend: Backend,
    path: Path,
    prompt: PromptVersion,
    *,
    out: TextIO,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Every sentence through extraction, each line added to ``path`` once it is done."""
    recorder = RecordingModel(backend.model)
    for number, sentence in enumerate(sentences, start=1):
        recorder.replies = []
        started = clock()
        result = extract(
            sentence.text,
            recorder,
            now=sentence.now,
            zone=sentence.zone,
            coins=BUILT_IN_TABLE,
            prompt=prompt,
            asks_again=DEFAULT_ASKS_AGAIN,
        )
        seconds = clock() - started
        line = sentence_line(sentence, result, recorder.replies, seconds)
        append_line(path, line)
        scores = line["scores"]
        assert isinstance(scores, dict)
        print(
            f"[{number}/{len(sentences)}] {sentence.id} {seconds:.2f} s {line['result']}: "
            f"{scores['drafts']} draft(s) for {scores['gold_trades']} gold trade(s), "
            f"{scores['whole_right']} whole right",
            file=out,
            flush=True,
        )


def _arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__)
    chosen_set = parser.add_mutually_exclusive_group()
    chosen_set.add_argument("--final-exam", action="store_true", help="run the final set instead")
    chosen_set.add_argument(
        "--set",
        default=Split.DEBUG.value,
        choices=[Split.DEBUG.value, Split.WRITINGS.value],
        help="the set to run: the debug set, or the writings set scored apart",
    )
    parser.add_argument("--prompt", default="first", choices=sorted(PROMPTS))
    parser.add_argument("--model", default=None, help="the model to ask instead of the setting")
    parser.add_argument("--only", nargs="+", default=None, help="only these sentence ids")
    parser.add_argument("--resume", type=Path, default=None, help="carry on this results file")
    return parser.parse_args(arguments)


def set_for(options: argparse.Namespace) -> tuple[Split, Path]:
    """The set a run takes: the debug set, unless the final-exam switch or ``--set`` says else."""
    if options.final_exam:
        return Split.FINAL, FINAL_SET
    if options.set == Split.WRITINGS.value:
        return Split.WRITINGS, WRITINGS_SET
    return Split.DEBUG, DEBUG_SET


def _results_path(results_dir: Path, split: Split, prompt: str, started: datetime) -> Path:
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    return results_dir / f"run-{stamp}-{split.value}-{prompt}.jsonl"


def _start_or_resume(
    options: argparse.Namespace,
    conditions: dict[str, object],
    started: datetime,
    results_dir: Path,
    out: TextIO,
) -> tuple[Path, set[str]] | None:
    if options.resume is None:
        results_dir.mkdir(parents=True, exist_ok=True)
        path = _results_path(results_dir, Split(str(conditions["set"])), options.prompt, started)
        append_line(path, conditions)
        return path, set()
    path = options.resume
    earlier = read_results(path)
    changed = [key for key in _SAME_TO_RESUME if earlier.run.get(key) != conditions.get(key)]
    if changed:
        print(f"cannot resume {path.name}: changed since it began: {', '.join(changed)}", file=out)
        return None
    if earlier.end is not None:
        print(f"{path.name} is already finished", file=out)
        return None
    with path.open("r+b") as stream:
        stream.truncate(earlier.complete_bytes)
    return path, {str(line["id"]) for line in earlier.sentences}


def main(
    arguments: Sequence[str],
    *,
    out: TextIO = sys.stdout,
    backend: Callable[[str | None], Backend] = local_backend,
    results_dir: Path = RESULTS_DIR,
) -> int:
    """Run the script; ``backend`` and ``results_dir`` stand in for the outside world in tests."""
    options = _arguments(arguments)
    split, set_file = set_for(options)
    sentences = load_set(set_file, split)
    if options.only:
        unknown = set(options.only) - {s.id for s in sentences}
        if unknown:
            print(f"not in the {split.value} set: {', '.join(sorted(unknown))}", file=out)
            return 2
        sentences = tuple(s for s in sentences if s.id in options.only)
    try:
        chosen = backend(options.model)
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    conditions = run_conditions(split, set_file, options.prompt, chosen, started)
    if options.only:
        conditions["only"] = list(options.only)
    begun = _start_or_resume(options, conditions, started, results_dir, out)
    if begun is None:
        return 2
    path, done = begun
    print(f"results: {_relative(path)}", file=out, flush=True)
    todo = [s for s in sentences if s.id not in done]
    clock_start = time.monotonic()
    run_sentences(todo, chosen, path, PROMPTS[options.prompt][0], out=out)
    finished = datetime.now(UTC)
    append_line(
        path,
        {
            "record": LineKind.END.value,
            "finished_at": finished.isoformat(timespec="seconds"),
            "sentences_this_session": len(todo),
            "seconds_this_session": round(time.monotonic() - clock_start, 3),
        },
    )
    summary = summarize(read_results(path))
    saved = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    summary_path(path).write_text(saved, encoding="utf-8")
    print(markdown(summary), file=out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
