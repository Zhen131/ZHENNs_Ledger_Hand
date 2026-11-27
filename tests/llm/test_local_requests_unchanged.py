"""With no model setting, what is sent to the local model is exactly what it was.

The golden file was captured on the code before the cloud services were
added (see ``local_requests``). Each request is compared as a whole: the
method, the address, every header and the body, byte for byte. The settings
page's line on the plug is compared too. These tests are not to be changed.
"""

from __future__ import annotations

import json

from tests.llm.local_requests import GOLDEN, capture


def _golden() -> dict[str, object]:
    loaded = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_the_default_settings_send_the_same_three_kinds_of_request() -> None:
    captured = capture()
    golden = _golden()

    assert len(captured["requests"]) == 3  # type: ignore[arg-type]
    assert captured["requests"] == golden["requests"]


def test_each_request_is_the_same_in_its_four_parts() -> None:
    captured = capture()["requests"]
    golden = _golden()["requests"]
    assert isinstance(captured, list)
    assert isinstance(golden, list)

    for now, before in zip(captured, golden, strict=True):
        for part in ("method", "url", "headers", "body"):
            assert now[part] == before[part], part


def test_the_settings_page_line_on_the_plug_is_the_same() -> None:
    assert capture()["plug_line"] == _golden()["plug_line"]
