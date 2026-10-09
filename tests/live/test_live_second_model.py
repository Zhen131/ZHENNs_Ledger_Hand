"""The live check of naming a model this machine does not have. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out; ``scripts/check.sh
live`` runs it against the model server the settings name. A run that
names a model the server does not have must stop before it writes any
results file, say that the model is not there, and exit with status 2, in
both ways of reading a passage. The server's list of models is read before
and after (``GET /api/tags``, which only reads) and must be the same: the
check downloads, copies and deletes nothing.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest

from evals import run as runner
from ledger_hand.llm.ollama_identity import MODELS_PATH
from ledger_hand.settings import load_model_settings

pytestmark = pytest.mark.live_model

# A name no model server is expected to have; the check makes sure of it first.
ABSENT = "no-such-model-for-the-check:0.1b"


def model_list() -> object:
    settings = load_model_settings()
    answer = httpx.get(settings.base_url + MODELS_PATH, timeout=settings.timeout_seconds)
    answer.raise_for_status()
    return answer.json()


@pytest.mark.parametrize("method", ["one_list", "split_first"])
def test_a_model_the_server_does_not_have_stops_the_run_before_any_file(
    method: str, tmp_path: Path
) -> None:
    before = model_list()
    names = {entry.get("name") for entry in before.get("models", [])}  # type: ignore[attr-defined]
    assert ABSENT not in names
    out = io.StringIO()

    status = runner.main(
        ["--model", ABSENT, "--method", method, "--only", "d24"], out=out, results_dir=tmp_path
    )

    print(f"\nmodels before: {sorted(str(name) for name in names)}")
    print(f"exit status:   {status}")
    print(f"said:          {out.getvalue().strip()}")
    assert status == 2
    assert "cannot start" in out.getvalue() and "does not have the model" in out.getvalue()
    assert list(tmp_path.iterdir()) == []
    assert model_list() == before
