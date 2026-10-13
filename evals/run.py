"""Run an experiment: every sentence of a set through extraction, each result saved as it comes.

    .venv/bin/python -m evals.run                      # the debug set, the first prompt
    .venv/bin/python -m evals.run --prompt first --model qwen2.5:7b
    .venv/bin/python -m evals.run --set writings --prompt stepwise
    .venv/bin/python -m evals.run --method split_first # split first, then extract
    .venv/bin/python -m evals.run --resume evals/results/<file>.jsonl

Run from the top of the repository. The model is the one the settings name
(see "Model settings" in the README), unless ``--model`` names another; the
parameters (temperature and the rest) are the settings' too. Only the local
plug is used: the run asks Ollama itself for the model's fingerprint, so
settings that choose the cloud plug (``LEDGER_HAND_MODEL_PLUG=cloud``) are
refused before anything is sent. The set is the debug set, unless ``--set``
names the writings set (``writings``), which is scored apart. The final set
is run only with ``--final-exam``, and the results file then says so: it is
kept for the last run of an experiment.

Each passage is read one of two ways (``--method``, see ``methods``): the
whole passage in one call (``one_list``, the default and the product's way),
or split into one segment per trade first, each extracted on its own
(``split_first``, see ``splitting``, with the split prompt ``split-1``).

For each sentence, extraction is given the sentence's own fixed moment and
zone, never the clock. The moment a sentence is done, its line is added to
the results file and written to disk, so a run cut short shows how far it
got; ``--resume`` carries it on from there, under the same conditions only.
When every sentence is done, an ``end`` line is added, the summary is worked
out afresh from the file (``tables``), saved beside it as
``<name>.summary.json`` and printed as tables.

The first line of the results file records the conditions of the run: the
set file and its fingerprint (SHA-256), the prompt version, its files and
their fingerprints, the fingerprint of the reply table it sends, the way of
reading a passage (and when it is split first, the split prompt, its file,
its fingerprints and the fingerprint of its table), the commit of the
repository and whether the work tree was clean, the model, its fingerprint
and the Ollama version (asked through the local plug's ``ask_identity``),
every parameter, and the moment the run began. Paths are written relative
to the repository. Each sentence's line holds, besides the drafts and the
replies, the record of every reply read (``reads``) and, when the passage
was split first, how it went (``split``): the route, the trades the split
listed and the segments.

Exit status: 0 the run finished; 2 it could not start (a wrong argument, a
setting, settings that choose the cloud plug, or the model server could not
say who it is).

Names defined here: ``main``, ``Backend``, ``RecordingModel``,
``PROMPTS``, ``SPLIT_PROMPT``, ``RESULTS_DIR``, ``Trace``,
``one_list_trace``, ``read_passage``, ``sentence_line`` and
``run_sentences``.
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
from evals.methods import Method, method_of
from evals.reads import copied_from_reads, reads_of
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
    split,
    stepwise,
    zero_shot,
)
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.split_table import SPLIT_TABLE, example_split_reply
from ledger_hand.extraction.splitting import (
    CallStep,
    Purpose,
    SplitExtraction,
    split_then_extract,
)
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
from ledger_hand.settings import ModelSettings, Plug, SettingsError, Variable, load_model_settings

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
    "method",
    "split_prompt_content_sha256",
    "split_table_sha256",
    "commit",
    "model",
    "model_fingerprint",
    "server_version",
    "parameters",
)
# The split prompt a run that splits first uses, and the file its words are in.
SPLIT_PROMPT = split.SPLIT_PROMPT
_SPLIT_FILES = (split,)


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
    """The model the settings name (or ``model_name``), asked who it is first.

    Raises ``SettingsError``, before anything is sent, when the settings
    choose a plug other than the local one.
    """
    settings = load_model_settings()
    if settings.plug is not Plug.LOCAL:
        raise SettingsError(
            f"{Variable.PLUG.value} is {settings.plug.value}, but the experiment tools use the "
            f"{Plug.LOCAL.value} plug only: they ask Ollama itself for the model's fingerprint. "
            f"Unset {Variable.PLUG.value}, or set it to {Plug.LOCAL.value}, to run them."
        )
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


def _split_prompt_content() -> str:
    examples = [[e.passage, example_split_reply(e)] for e in SPLIT_PROMPT.examples]
    content = [SPLIT_PROMPT.instructions, examples, SPLIT_PROMPT.ask_again]
    return json.dumps(content, ensure_ascii=False)


def _files(modules: Sequence[ModuleType]) -> list[dict[str, str]]:
    paths = [Path(str(module.__file__)) for module in modules]
    return [{"path": _relative(f), "sha256": _sha256(f.read_bytes())} for f in paths]


def _method_conditions(method: Method) -> dict[str, object]:
    """The way of reading a passage; and when it splits first, what the split sends."""
    if method is Method.ONE_LIST:
        return {"method": method.value}
    table = json.dumps(SPLIT_TABLE, ensure_ascii=False)
    return {
        "method": method.value,
        "split_prompt": SPLIT_PROMPT.name,
        "split_prompt_files": _files(_SPLIT_FILES),
        "split_prompt_content_sha256": _sha256(_split_prompt_content().encode("utf-8")),
        "split_table_sha256": _sha256(table.encode("utf-8")),
    }


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
    split: Split,
    set_file: Path,
    prompt_name: str,
    backend: Backend,
    started: datetime,
    method: Method = Method.ONE_LIST,
) -> dict[str, object]:
    """The first line of a results file: everything the run's numbers depend on."""
    prompt, modules = PROMPTS[prompt_name]
    return {
        "record": LineKind.RUN.value,
        "set": split.value,
        "final_exam_switch": split is Split.FINAL,
        "set_file": _relative(set_file),
        "set_sha256": _sha256(set_file.read_bytes()),
        "prompt": prompt_name,
        "prompt_files": _files(modules),
        "prompt_content_sha256": _sha256(_prompt_content(prompt).encode("utf-8")),
        "reply_table_sha256": _sha256(_reply_table(prompt).encode("utf-8")),
        **_method_conditions(method),
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


@dataclass(frozen=True)
class Trace:
    """What each call of one passage was for, the calls the drafts came from, and the split."""

    steps: tuple[CallStep, ...]
    draft_calls: tuple[int, ...]
    split: SplitExtraction | None = None


def one_list_trace(result: Extraction) -> Trace:
    """The trace of a passage read in one call: every call an extraction of the whole passage."""
    calls = () if isinstance(result, PassageRefused) else result.calls
    steps = tuple(CallStep(Purpose.EXTRACT, None) for _ in calls)
    last = (len(calls) - 1,) if isinstance(result, Extracted) else ()
    return Trace(steps, last)


def _split_record(done: SplitExtraction) -> dict[str, object]:
    return {
        "route": done.route.name,
        "fell_back": done.route.fell_back,
        "trades_listed": done.trades_listed,
        "segments": list(done.segments),
    }


def _produced(result: Extraction, copied: Sequence[Mapping[Field, str]]) -> Produced:
    if isinstance(result, Extracted):
        return Produced(ResultKind.EXTRACTED, result.drafts, result.issues, tuple(copied))
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
    sentence: Sentence,
    result: Extraction,
    replies: Sequence[ModelReply],
    seconds: float,
    trace: Trace | None = None,
) -> dict[str, object]:
    """The results-file line of one sentence; without ``trace``, read in one call."""
    traced = one_list_trace(result) if trace is None else trace
    reads = reads_of(replies, traced.steps, traced.draft_calls)
    produced = _produced(result, copied_from_reads(reads))
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
        "reads": reads,
        "issues": [issue_to_json(issue) for issue in produced.issues],
        "seconds": round(seconds, 3),
        "scores": score_to_json(score_sentence(sentence, produced)),
    }
    if traced.split is not None:
        line["split"] = _split_record(traced.split)
    if sentence.group is Group.NOT_TO_RECORD:
        line["checks"] = _checks(sentence, produced)
    return line


def read_passage(
    sentence: Sentence, model: ModelPort, prompt: PromptVersion, method: Method
) -> tuple[Extraction, Trace]:
    """What the passage of ``sentence`` gave, read the way ``method`` names, and its trace."""
    if method is Method.SPLIT_FIRST:
        done = split_then_extract(
            sentence.text,
            model,
            now=sentence.now,
            zone=sentence.zone,
            coins=BUILT_IN_TABLE,
            prompt=prompt,
            split_prompt=SPLIT_PROMPT,
            asks_again=DEFAULT_ASKS_AGAIN,
        )
        return done.extraction, Trace(done.steps, done.draft_calls, done)
    result = extract(
        sentence.text,
        model,
        now=sentence.now,
        zone=sentence.zone,
        coins=BUILT_IN_TABLE,
        prompt=prompt,
        asks_again=DEFAULT_ASKS_AGAIN,
    )
    return result, one_list_trace(result)


def run_sentences(
    sentences: Sequence[Sentence],
    backend: Backend,
    path: Path,
    prompt: PromptVersion,
    *,
    out: TextIO,
    clock: Callable[[], float] = time.monotonic,
    method: Method = Method.ONE_LIST,
) -> None:
    """Every sentence through extraction, each line added to ``path`` once it is done."""
    recorder = RecordingModel(backend.model)
    for number, sentence in enumerate(sentences, start=1):
        recorder.replies = []
        started = clock()
        result, trace = read_passage(sentence, recorder, prompt, method)
        seconds = clock() - started
        line = sentence_line(sentence, result, recorder.replies, seconds, trace)
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
    parser.add_argument(
        "--method",
        default=Method.ONE_LIST.value,
        choices=[method.value for method in Method],
        help="read each passage in one call, or split it into one segment per trade first",
    )
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


def _results_path(
    results_dir: Path, split: Split, prompt: str, started: datetime, method: Method
) -> Path:
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    way = "" if method is Method.ONE_LIST else f"-{method.value}"
    return results_dir / f"run-{stamp}-{split.value}-{prompt}{way}.jsonl"


def _start_or_resume(
    options: argparse.Namespace,
    conditions: dict[str, object],
    started: datetime,
    results_dir: Path,
    out: TextIO,
) -> tuple[Path, set[str]] | None:
    if options.resume is None:
        results_dir.mkdir(parents=True, exist_ok=True)
        split = Split(str(conditions["set"]))
        path = _results_path(results_dir, split, options.prompt, started, Method(options.method))
        append_line(path, conditions)
        return path, set()
    path = options.resume
    earlier = read_results(path)
    # A run line without a method was made before there was a choice: one list.
    before = {**earlier.run, "method": method_of(earlier.run).value}
    changed = [key for key in _SAME_TO_RESUME if before.get(key) != conditions.get(key)]
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
    method = Method(options.method)
    conditions = run_conditions(split, set_file, options.prompt, chosen, started, method)
    if options.only:
        conditions["only"] = list(options.only)
    begun = _start_or_resume(options, conditions, started, results_dir, out)
    if begun is None:
        return 2
    path, done = begun
    print(f"results: {_relative(path)}", file=out, flush=True)
    todo = [s for s in sentences if s.id not in done]
    clock_start = time.monotonic()
    run_sentences(todo, chosen, path, PROMPTS[options.prompt][0], out=out, method=method)
    _finish(path, len(todo), time.monotonic() - clock_start, out)
    return 0


def _finish(path: Path, sentences: int, seconds: float, out: TextIO) -> None:
    """The end line, and the summary worked out from the file, saved beside it and printed."""
    finished = datetime.now(UTC)
    append_line(
        path,
        {
            "record": LineKind.END.value,
            "finished_at": finished.isoformat(timespec="seconds"),
            "sentences_this_session": sentences,
            "seconds_this_session": round(seconds, 3),
        },
    )
    summary = summarize(read_results(path))
    saved = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    summary_path(path).write_text(saved, encoding="utf-8")
    print(markdown(summary), file=out)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
