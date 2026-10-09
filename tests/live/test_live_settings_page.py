"""The live check of the settings page: an address nobody listens on, then back. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out; ``scripts/check.sh
live`` runs it. The page is run headless with nothing put in its session,
so it builds its parts with the wiring module, as when it is started for
real, with the data folder in a temporary folder.

On the settings page the model's address is changed to a port on this
machine that nobody listens on, found by asking the system for a free one;
the model server itself is never stopped. A passage typed then must be
answered by the sentence that names that address. Back to the environment
and the defaults, the same passage must come to its first question, or to
every trade settled, from the real model. What was said is printed, so the
run itself is the record.
"""

from __future__ import annotations

import socket
import time
from contextlib import closing
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.settings import DATA_DIRECTORY_VARIABLE, Variable, load_model_settings
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.ui.settings_form import NOTE_KEY
from tests.ui.app_harness import APP_FILE, program_said, send
from tests.ui.page_harness import apply, note, reset, set_setting, to_record, to_settings

pytestmark = pytest.mark.live_model

REPO_ROOT = Path(__file__).resolve().parents[2]
PASSAGE = "Bought 0.02 BTC at 94,900 yesterday"
# Judging, extraction and wording a question, each with room to retry.
SECONDS_ALLOWED = 600


def unused_port() -> int:
    """A port on this machine that nobody listens on: one the system just handed out, let go."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert isinstance(port, int)
    return port


def test_an_address_nobody_listens_on_is_named_and_going_back_works_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(tmp_path / "data"))
    data_in_repo_before = (REPO_ROOT / "data").exists()
    page = AppTest.from_file(str(APP_FILE), default_timeout=SECONDS_ALLOWED).run()
    assert not page.exception
    assert not page.error, [error.value for error in page.error]
    nobody = f"http://127.0.0.1:{unused_port()}"

    page = apply(set_setting(to_settings(page), Variable.URL, nobody))
    print(f"\nsettings page: {note(page, NOTE_KEY)}")
    began = time.monotonic()
    page = send(to_record(page), PASSAGE)
    took = time.monotonic() - began

    said = program_said(page)[-1]
    print(f"passage: {PASSAGE!r}\nthe program said: {said!r}\ntime taken: {took:.1f} s")
    assert not page.exception
    assert said.startswith("The model gave no usable reply while judging the passage")
    assert f"No model answered at {nobody}." in said

    page = reset(to_settings(page))
    back = page.session_state[PARTS_KEY].settings.base_url
    print(f"settings page: {note(page, NOTE_KEY)}")
    assert back == load_model_settings().base_url
    began = time.monotonic()
    page = send(to_record(page), PASSAGE)
    took = time.monotonic() - began

    said = program_said(page)[-1]
    print(f"address: {back}\nthe program said: {said!r}\ntime taken: {took:.1f} s")
    assert not page.exception
    if said.startswith("The model gave no usable reply"):
        pytest.fail(f"the live check could not talk to the model: {said}", pytrace=False)
    assert said.startswith(("[Trade 1 of ", "Every trade is settled")), said
    assert (REPO_ROOT / "data").exists() == data_in_repo_before
