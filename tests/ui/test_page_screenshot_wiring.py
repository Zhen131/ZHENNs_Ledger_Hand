"""Tests of the screenshot area on a page whose parts the wiring module built.

With the local plug, the parts hold the vision model and its check, so the
upload box is there, and opening the page asks the server nothing. With the
cloud plug, the box is there too, and a screenshot uploaded is answered in
the chat without a request to anyone. Every value here is invented.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.flows.uploading import UploadNotRead, UploadProblem
from ledger_hand.settings import Variable
from ledger_hand.ui.failure_words import screenshot_not_read
from ledger_hand.wiring import Parts
from tests.fakes.routed_model import RoutedModel
from tests.ui.app_harness import APP_FILE, PARTS_KEY, program_said
from tests.ui.page_harness import Builds, open_built
from tests.ui.screenshot_harness import PNG, upload, upload_box

KEY = "sk-invented-page-wiring-0123456789"


def test_the_built_page_offers_the_upload_box_and_asks_nothing(
    bare_machine: Path, tmp_path: Path
) -> None:
    page = AppTest.from_file(str(APP_FILE), default_timeout=30).run()

    assert not page.exception
    assert not page.error
    parts = page.session_state[PARTS_KEY]
    assert isinstance(parts, Parts)
    assert parts.vision_model is not None and parts.vision_check is not None
    assert not upload_box(page).disabled
    assert list(tmp_path.iterdir()) == []


def test_with_the_cloud_plug_an_upload_is_answered_and_nothing_is_sent(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "cloud")
    monkeypatch.setenv(Variable.URL.value, "https://api.example.com/v1")
    monkeypatch.setenv(Variable.KEY.value, KEY)
    routed = RoutedModel()
    builds = Builds(routed)
    page = open_built(builds)
    (parts,) = builds.built
    assert (parts.vision_model, parts.vision_check) == (None, None)

    page = upload(page, PNG)

    assert not page.exception
    expected = UploadNotRead(UploadProblem.CLOUD_PLUG, len(PNG), parts.settings.screenshot_max_mb)
    assert program_said(page) == [screenshot_not_read(expected, parts.settings)]
    assert all(model.used == [] for model in builds.models)
    assert routed.pictures.calls == []
