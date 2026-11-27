"""Measure the extraction sets through the start of recording, judging step and all.

    .venv/bin/python -m evals.judged_run --screen screen-1
    .venv/bin/python -m evals.judged_run --screen screen-2 --final-exam
    .venv/bin/python -m evals.judged_run --screen screen-2 --extract first-3 --hold-other-unit
    .venv/bin/python -m evals.judged_run --screen screen-2 --extract first-3 --hold-other-unit \
        --voice --tidy

Run from the top of the repository. Every sentence of the debug set (or,
with ``--final-exam``, of the final set, or with ``--voice``, of the voice
set) goes through ``recording.start``
with the built-in asset table (the coins of the coin table and USDT), the
judging prompt version ``--screen`` names and the extraction version
``--extract`` names (``first`` unless said), at the sentence's own moment
and zone; nothing is asked or answered after that. The drafts the flow
holds then, and the issues extraction raised, are scored against the gold
answer exactly as ``evals.run`` scores extraction alone (``scoring``). A
passage the judging step stops, or finds no trade in, gives no draft.

With ``--hold-other-unit`` the flow is started as the assistant starts
it: a trade whose quantity carries a unit that is not the trade's asset
is held back at once (``recording.start``, ``hold_other_unit``). Nothing
it scores changes, since the drafts are scored as extracted; the line of
each sentence also says which trades were held. Each line says, for
every draft, which kinds of reminder it carries (``draft_reminders``)
and whether it came out right in every field (``draft_whole_right``),
and which kinds of reminder are about the passage as a whole
(``passage_reminders``), so that what holding back takes away can be
counted afterwards.

With ``--tidy`` each sentence is first tidied as the assistant tidies what
is said (``spoken_text.tidy_spoken``, in the sentence's own zone), and the
tidied words go to the flow. The gold answers are scored as before: a gold
phrase is a piece of the sentence as written, and a field is scored by its
value, never by the phrase copied. The first line says ``"tidy": true`` and
the fingerprint of the tidying module; each line says which kinds of change
were made to its sentence (``tidied``), and the file's name ends in
``-tidy``. Without ``--tidy`` the sentence goes to the flow exactly as
written, and nothing in the results differs from a run before the switch
was added. (Decided on 2026-11-25.)

A version written for Chinese (``CHINESE_EXTRACTS``, ``spoken-1`` and
after) is not handed every sentence: each passage goes through the one
function the assistant asks (``prompt_language.extract_prompt_for``), so a
passage with a Chinese character in it is extracted with the version named
and one with none with ``first-3``; the first line then says
``"english_extraction_prompt": "first-3"`` as well. Any other version is
handed every sentence, as before.

It is here so that a new prompt version the assistant uses can be held to
the old sentences: on the same day, each version runs both sets, and the
fields wrong with nothing said about them (``silent_wrong``: a wrong value
with no issue, or a value made up with no issue, as ``tables`` counts
them) are compared. This runner changes nothing of ``evals.run`` and is
not one of its versions.

The results go into ``evals/tool_results/``, never ``evals/results/``: a
first line with the conditions, one line for each sentence, and an
``end`` line with the counts.

Exit status: 0 the run finished; 2 it could not start, or ``--voice`` and
``--final-exam`` were both given.

Names defined here: ``SCREENS``, ``EXTRACTS``, ``CHINESE_EXTRACTS``, ``produced_of``,
``silent_wrong``, ``reminders_of``, ``whole_right_of``, ``held_of``,
``run`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from evals.cells import CellOutcome
from evals.gold import DEBUG_SET, FINAL_SET, Sentence, Split, load_set
from evals.run import Backend, local_backend
from evals.scoring import Produced, ResultKind, SentenceScore, score_sentence
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from evals.voice import VOICE_SET
from ledger_hand.core import spoken_text
from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.spoken_text import tidy_spoken
from ledger_hand.extraction.prompt_language import ENGLISH_EXTRACT_PROMPT, extract_prompt_for
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first2 import FIRST_PROMPT_2
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.extraction.prompts.spoken1 import SPOKEN_PROMPT_1
from ledger_hand.extraction.prompts.spoken2 import SPOKEN_PROMPT_2
from ledger_hand.extraction.prompts.spoken3 import SPOKEN_PROMPT_3
from ledger_hand.flows.progress import Progress, Stage, TradeStatus
from ledger_hand.flows.recording import start
from ledger_hand.ports import ModelError, ModelPort
from ledger_hand.settings import SettingsError

SCREENS: dict[str, PromptVersion] = {
    SCREEN_PROMPT.name: SCREEN_PROMPT,
    SCREEN_PROMPT_2.name: SCREEN_PROMPT_2,
}
# The versions written for words with Chinese in them; English is read with first-3.
_BY_LANGUAGE: dict[str, PromptVersion] = {
    SPOKEN_PROMPT_1.name: SPOKEN_PROMPT_1,
    SPOKEN_PROMPT_2.name: SPOKEN_PROMPT_2,
    SPOKEN_PROMPT_3.name: SPOKEN_PROMPT_3,
}
# The versions a measure may hand the assistant for Chinese: first-3 is
# "keep what there is", since first-3 for Chinese gives first-3 for all.
CHINESE_EXTRACTS: dict[str, PromptVersion] = {
    FIRST_PROMPT_3.name: FIRST_PROMPT_3,
    **_BY_LANGUAGE,
}
EXTRACTS: dict[str, PromptVersion] = {
    FIRST_PROMPT.name: FIRST_PROMPT,
    FIRST_PROMPT_2.name: FIRST_PROMPT_2,
    FIRST_PROMPT_3.name: FIRST_PROMPT_3,
    **_BY_LANGUAGE,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def produced_of(progress: Progress) -> Produced:
    """What the start of recording gave, as the scorer takes it."""
    if progress.stage is Stage.FAILED:
        return Produced(ResultKind.MODEL_FAILED)
    if progress.stage is Stage.REFUSED:
        return Produced(ResultKind.PASSAGE_REFUSED)
    drafts = tuple(trade.draft for trade in progress.trades)
    return Produced(ResultKind.EXTRACTED, drafts, progress.issues)


def silent_wrong(score: SentenceScore) -> int:
    """The fields wrong with nothing said: a wrong value, or a made-up one, with no issue."""
    return sum(
        1
        for pair in score.pairs
        for cell in pair.cells
        if cell.outcome is CellOutcome.WRONG_SILENT
        or (cell.outcome is CellOutcome.MADE_UP and not cell.issues)
    )


def _one(
    sentence: Sentence,
    model: ModelPort,
    screen: PromptVersion,
    extract: PromptVersion,
    *,
    hold: bool = False,
    tidy: bool = False,
) -> Progress:
    passage = _passage(sentence, tidy=tidy)
    if extract.name in _BY_LANGUAGE:
        extract = extract_prompt_for(passage, extract)
    return start(
        passage,
        model,
        now=sentence.now,
        zone=sentence.zone,
        assets=BUILT_IN_ASSETS,
        screen_prompt=screen,
        extract_prompt=extract,
        hold_other_unit=hold,
    )


def _passage(sentence: Sentence, *, tidy: bool) -> str:
    """What the flow is handed: the sentence as written, or tidied as the assistant tidies it."""
    return tidy_spoken(sentence.text, sentence.zone).text if tidy else sentence.text


def reminders_of(progress: Progress) -> tuple[list[list[str]], list[str]]:
    """The kinds of reminder about each draft, and those about the passage, by name."""
    by_draft: list[list[str]] = [[] for _ in progress.trades]
    passage: list[str] = []
    for issue in progress.reminders:
        kinds = passage if issue.draft is None else by_draft[issue.draft]
        if issue.kind.name not in kinds:
            kinds.append(issue.kind.name)
    return [sorted(kinds) for kinds in by_draft], sorted(passage)


def whole_right_of(score: SentenceScore, drafts: int) -> list[bool]:
    """For each draft, whether it was paired with a gold trade and right in every field."""
    right = [False] * drafts
    for pair in score.pairs:
        right[pair.draft_at] = pair.whole
    return right


def held_of(progress: Progress) -> list[int]:
    """The positions, from 0, of the trades held back at the start, before any question."""
    return [
        position
        for position, trade in enumerate(progress.trades)
        if trade.status is TradeStatus.CANNOT_RECORD and trade.reason is None
    ]


def run(
    sentences: Sequence[Sentence],
    backend: Backend,
    path: Path,
    screen: PromptVersion,
    extract: PromptVersion,
    *,
    hold: bool = False,
    tidy: bool = False,
) -> dict[str, object]:
    """Every sentence through the start of recording; each line added as it is done."""
    totals = {"sentences": 0, "gold_trades": 0, "whole_right": 0, "silent_wrong": 0}
    judged_no_trade = 0
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for sentence in sentences:
            began = time.monotonic()
            progress = _one(sentence, backend.model, screen, extract, hold=hold, tidy=tidy)
            score = score_sentence(sentence, produced_of(progress))
            wrong = silent_wrong(score)
            totals["sentences"] += 1
            totals["gold_trades"] += score.gold_trades
            totals["whole_right"] += score.whole_right
            totals["silent_wrong"] += wrong
            if sentence.trades and progress.stage in (Stage.STOPPED, Stage.NO_TRADE):
                judged_no_trade += 1
            line = {
                "record": "sentence",
                "id": sentence.id,
                "stage": progress.stage.value,
                "drafts": len(progress.trades),
                "gold_trades": score.gold_trades,
                "whole_right": score.whole_right,
                "silent_wrong": wrong,
                "seconds": round(time.monotonic() - began, 1),
            }
            by_draft, passage = reminders_of(progress)
            line["draft_reminders"] = by_draft
            line["passage_reminders"] = passage
            line["draft_whole_right"] = whole_right_of(score, len(progress.trades))
            line["held"] = held_of(progress)
            if tidy:
                changes = tidy_spoken(sentence.text, sentence.zone).changes
                line["tidied"] = sorted({change.kind.name for change in changes})
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
    return {**totals, "gold_trades_judged_away": judged_no_trade}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evals.judged_run")
    parser.add_argument("--screen", choices=sorted(SCREENS), required=True)
    parser.add_argument("--extract", choices=sorted(EXTRACTS), default=FIRST_PROMPT.name)
    parser.add_argument("--final-exam", action="store_true", help="run the final set")
    parser.add_argument("--voice", action="store_true", help="run the voice set")
    parser.add_argument(
        "--tidy",
        action="store_true",
        help="tidy each sentence first, as the assistant tidies what is said",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--hold-other-unit",
        action="store_true",
        help="hold back a trade whose quantity carries another unit, as the assistant does",
    )
    return parser


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run one version on one set; print the counts."""
    options = _parser().parse_args(arguments)
    if options.voice and options.final_exam:
        print("cannot start: --voice and --final-exam name two sets; give one", file=out)
        return 2
    set_file, split = _set_of(options)
    screen, extract = SCREENS[options.screen], EXTRACTS[options.extract]
    try:
        backend = local_backend(options.model)
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    held = "-hold" if options.hold_other_unit else ""
    tidied = "-tidy" if options.tidy else ""
    name = f"judged-{stamp}-{split.value}-{screen.name}-{extract.name}{held}{tidied}.jsonl"
    path = TOOL_RESULTS_DIR / name
    head = _head(options, set_file, backend, started)
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    end = {
        "record": "end",
        **run(
            load_set(set_file, split),
            backend,
            path,
            screen,
            extract,
            hold=options.hold_other_unit,
            tidy=options.tidy,
        ),
    }
    with path.open("a", encoding="utf-8", newline="\n") as tail:
        tail.write(json.dumps(end, ensure_ascii=False) + "\n")
    print(f"results: {_shown(path)}", file=out)
    print(json.dumps(end, ensure_ascii=False), file=out)
    return 0


def _head(
    options: argparse.Namespace, set_file: Path, backend: Backend, started: datetime
) -> dict[str, object]:
    """The first line of a results file: everything the run's numbers depend on."""
    results = _shown(TOOL_RESULTS_DIR)
    head: dict[str, object] = {
        "record": "run",
        "set_file": set_file.relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "screen_prompt": SCREENS[options.screen].name,
        "extraction_prompt": EXTRACTS[options.extract].name,
        "asset_table": "built-in: the coin table's coins, priced in USDT",
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "parameters": dict(backend.parameters),
        "started_at": started.isoformat(timespec="seconds"),
        "hold_other_unit": options.hold_other_unit,
    }
    if options.extract in _BY_LANGUAGE:
        head["english_extraction_prompt"] = ENGLISH_EXTRACT_PROMPT.name
    if options.tidy:
        head["tidy"] = True
        head["tidy_module_sha256"] = _sha256(Path(spoken_text.__file__).read_bytes())
    return head


def _set_of(options: argparse.Namespace) -> tuple[Path, Split]:
    if options.final_exam:
        return FINAL_SET, Split.FINAL
    if options.voice:
        return VOICE_SET, Split.VOICE
    return DEBUG_SET, Split.DEBUG


def _shown(path: Path) -> str:
    """``path`` from the top of the repository, or whole when it lies elsewhere (a test's)."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
