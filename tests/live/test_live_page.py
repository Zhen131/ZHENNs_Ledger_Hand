"""The live smoke test of the page: one invented passage through the real parts. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out; ``scripts/check.sh
live`` runs it. The page is run headless with nothing put in its session,
so it builds its parts with the wiring module, as when it is started for
real: the model the settings name, the machine's clock and zone, and the
book in the data folder, which is pointed at a temporary folder here so that
no ``data/`` appears in the repository.

One invented passage is sent. The page must not break, and it must come to
its first question or to every trade settled; what the program said, the
table and the time taken are printed, so the run itself is the record.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.settings import DATA_DIRECTORY_VARIABLE
from tests.ui.app_harness import APP_FILE, program_said, send, table

pytestmark = pytest.mark.live_model

REPO_ROOT = Path(__file__).resolve().parents[2]
PASSAGE = "Bought 0.02 BTC at 94,900 yesterday"
# Judging, extraction and wording a question, each with room to retry.
SECONDS_ALLOWED = 600


def test_one_passage_reaches_its_first_question_or_is_settled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(tmp_path / "data"))
    data_in_repo_before = (REPO_ROOT / "data").exists()
    page = AppTest.from_file(str(APP_FILE), default_timeout=SECONDS_ALLOWED).run()
    assert not page.exception
    assert not page.error, [error.value for error in page.error]

    began = time.monotonic()
    page = send(page, PASSAGE)
    took = time.monotonic() - began

    said = program_said(page)
    print(f"\npassage: {PASSAGE!r}\nthe program said: {said}\ntable: {table(page)}")
    print(f"time taken: {took:.1f} s")
    assert not page.exception
    assert said, "the program said nothing"
    if said[-1].startswith("The model gave no usable reply"):
        pytest.fail(f"the live check could not talk to the model: {said[-1]}", pytrace=False)
    assert said[-1].startswith(("[Trade 1 of ", "Every trade is settled")), said[-1]
    assert (REPO_ROOT / "data").exists() == data_in_repo_before
