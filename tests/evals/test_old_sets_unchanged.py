"""Gate: a set with no ``book`` and no ``half`` runs, writes and prints as before the two keys.

The two measures that go through the whole assistant for questions about
the ledger (``ask_run``) and for changes (``edit_run``) learnt to read two
keys at the top of a set file: which book to hold (``book``) and whether
the set is a hidden half (``half``). The sets written before them carry
neither, and must come out exactly as before. Each is run here with a
stand-in model that does the same thing every turn (looks up the holdings
and answers; or asks to delete a BTC trade), into a folder of its own; the
results file and the printed table, with the parts that change at every
run blanked, must have the fingerprints the earlier code gave them, pinned
below. No real model is called.

The system prompt a measure names is held at ``assistant-4`` while a
fingerprint is taken: the fingerprints were pinned when it was the
default, and the results file and the table name it, so a later default
would change them without changing how a set without the two keys runs.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

import evals.ask_run as ask_run
import evals.edit_run as edit_run
from evals.run import Backend
from ledger_hand.assistant.prompts.assistant_fourth import ASSISTANT_FOURTH
from ledger_hand.flows import assisting
from ledger_hand.ports import ChatItem, ModelParameters, ToolCall, ToolReply, ToolResult, ToolSpec
from tests.fakes.scripted_model import scripted_record

SETS = Path(__file__).resolve().parents[2] / "evals" / "sets"
CHANGING_IN_HEAD = ("commit", "worktree_clean", "model_fingerprint", "server_version", "started_at")
CHANGING_IN_SENTENCE = ("seconds",)
_STAMP = re.compile(r"\d{8}T\d{6}Z")

# The fingerprint of each run, taken with the code before the two keys.
PINNED = {
    ("ask", "asks.json"): "bb6256997e80f4f3656673677c3dbebc7c3fdd129b7c53f38332c547579c7e8c",
    ("ask", "asks_times.json"): (
        "44c8c86abab34a2eb95da2407d7e470e43154947cba11ec8fe17d76ba5515583"
    ),
    ("edit", "edits.json"): "1ad0740fd55fb01b3ebe5e551c81c497f6f16310a5c500318fce4d2a105ac594",
}


class _SameEveryTurn:
    """A stand-in model: one tool call, then, once its result is back, a few words."""

    def __init__(self, call: ToolCall) -> None:
        self._call = call

    def chat_with_tools(
        self,
        items: Sequence[ChatItem],
        tools: Sequence[ToolSpec],
        *,
        parameters: ModelParameters | None = None,
    ) -> ToolReply:
        if items and isinstance(items[-1], ToolResult):
            return ToolReply(text="Here it is.", calls=(), record=scripted_record())
        return ToolReply(text="", calls=(self._call,), record=scripted_record())


def _blanked(line: dict[str, object]) -> dict[str, object]:
    changing = CHANGING_IN_HEAD if line.get("record") == "run" else CHANGING_IN_SENTENCE
    return {key: (None if key in changing else value) for key, value in line.items()}


def _fingerprint(
    measure: str, set_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    module = ask_run if measure == "ask" else edit_run
    call = (
        ToolCall(name="get_positions", arguments={})
        if measure == "ask"
        else ToolCall(name="propose_trade_delete", arguments={"asset": "BTC"})
    )
    root = tmp_path / "repo"
    (root / "evals" / "sets").mkdir(parents=True)
    set_file = root / "evals" / "sets" / set_name
    shutil.copyfile(SETS / set_name, set_file)
    results = root / "evals" / "tool_results"
    backend = Backend(
        model=_SameEveryTurn(call),  # type: ignore[arg-type]
        name="stand-in",
        fingerprint="-",
        server_version="-",
        base_url="-",
        parameters={},
    )
    monkeypatch.setattr(module, "REPO_ROOT", root)
    monkeypatch.setattr(module, "TOOL_RESULTS_DIR", results)
    monkeypatch.setattr(module, "local_backend", lambda _name: backend)
    monkeypatch.setattr(module, "load_assistant_steps", lambda: 6)
    monkeypatch.setattr(assisting, "DEFAULT_PROMPT", ASSISTANT_FOURTH)
    out = io.StringIO()
    assert module.main(["--set", str(set_file)], out=out) == 0
    (written,) = results.glob("*.jsonl")
    lines = [_blanked(json.loads(line)) for line in written.read_text("utf-8").splitlines()]
    printed = _STAMP.sub("STAMP", out.getvalue())
    whole = json.dumps({"lines": lines, "printed": printed}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(whole.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(("measure", "set_name"), sorted(PINNED))
def test_a_set_without_the_two_keys_comes_out_as_before(
    measure: str, set_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _fingerprint(measure, set_name, tmp_path, monkeypatch) == PINNED[(measure, set_name)]
