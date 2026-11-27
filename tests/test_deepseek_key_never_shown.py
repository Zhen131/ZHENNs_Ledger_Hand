"""DeepSeek's key never shows: not whole, and not as the last four characters DeepSeek writes back.

The key here is invented and set in ``DEEPSEEK_API_KEY``. A fake DeepSeek
writes it back in every answer and in every error it raises, both whole
and the way DeepSeek wrote a refused key on 2026-11-27 ("****" and its last
four characters), and fails in each way the pages have a sentence for. No
form of it is then found anywhere this program shows or keeps text: the
pages' text, the record on this machine, the log and what is printed, the
text and the ``repr`` of every error, the settings' ``repr``, the try-out
script's output, and an experiment's results file. The first test checks
that the key really is sent, so the others cannot pass by never sending it.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from evals import run as runner
from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.cloud import CloudModel, forget_dropped_formats
from ledger_hand.llm.connect import connect_model
from ledger_hand.ports import Message, ModelError, Role
from ledger_hand.settings import (
    ENV_PREFIX,
    DataPlaces,
    ModelSettings,
    Variable,
    effective_settings,
    load_model_settings,
)
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.wiring import Parts
from scripts import try_assistant
from tests.llm.fake_server import mock_transport
from tests.ui.app_harness import APP_FILE, send
from tests.ui.assistant_harness import CountingBook, say_on_page
from tests.ui.page_harness import every_text

KEY = "sk-invented-never-shown-0123456789wxyz"
FORMS = (KEY, f"****{KEY[-4:]}", KEY[-4:])
WHOLE = json.dumps({"error": {"message": f"Authentication Fails, your api key: ****{KEY[-4:]} "}})


def echoed(status: int, headers: dict[str, str] | None = None) -> Callable[[], httpx.Response]:
    def make() -> httpx.Response:
        body = WHOLE[:-2] + f' and {KEY}"}}}}'
        return httpx.Response(status, content=body.encode("utf-8"), headers=headers or {})

    return make


def raising(error: type[Exception]) -> Callable[[], httpx.Response]:
    def make() -> httpx.Response:
        raise error(f"failed with Bearer {KEY} (****{KEY[-4:]})")

    return make


FAILURES: dict[str, Callable[[], httpx.Response]] = {
    "unreachable": raising(httpx.ConnectError),
    "timed out": raising(httpx.ReadTimeout),
    "no money": echoed(402),
    "key 401": echoed(401),
    "key 403": echoed(403),
    "too often, a wait": echoed(429, {"Retry-After": "2"}),
    "too often": echoed(429),
    "no such model": lambda: httpx.Response(
        400,
        content=json.dumps(
            {
                "error": {
                    "message": "The supported API model names are deepseek-flash, "
                    f"deepseek-v4-pro, but you passed deepseek-v4-pro. ****{KEY[-4:]}"
                }
            }
        ).encode("utf-8"),
    ),
}


@pytest.fixture(autouse=True)
def deepseek_with_the_invented_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    import os

    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.setenv(Variable.PLUG.value, "deepseek")
    monkeypatch.setenv(Variable.DEEPSEEK_KEY.value, KEY)
    monkeypatch.setenv(Variable.RETRIES.value, "0")
    forget_dropped_formats()
    yield
    forget_dropped_formats()


def transport(failure: str, seen: list[str] | None = None) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request.headers["authorization"])
        return FAILURES[failure]()

    return mock_transport(answer)


def settings() -> ModelSettings:
    return effective_settings(load_model_settings())


def assert_none_in(text: str) -> None:
    for form in FORMS:
        assert form not in text, form


def test_the_key_is_really_sent() -> None:
    seen: list[str] = []

    with pytest.raises(ModelError):
        connect_model(settings(), transport=transport("key 401", seen)).chat(
            [Message(Role.USER, "hi")]
        )

    assert seen == [f"Bearer {KEY}"]


@pytest.mark.parametrize("failure", list(FAILURES))
def test_no_error_shows_it(failure: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    model = connect_model(settings(), transport=transport(failure), sleep=lambda _: None)

    with pytest.raises(ModelError) as caught:
        model.chat([Message(Role.USER, "hi")], reply_schema={"type": "object"})
    with pytest.raises(ModelError) as caught_with_tools:
        model.chat_with_tools([Message(Role.USER, "hi")], _tools())

    for error in (caught.value, caught_with_tools.value):
        assert_none_in(str(error))
        assert_none_in(repr(error))
        assert_none_in(error.snippet or "")
    assert_none_in(caplog.text)
    assert_none_in(repr(settings()))


def _tools() -> list[object]:
    from ledger_hand.assistant.tools import tool_specs

    return list(tool_specs())


def page_with(failure: str, data: Path) -> AppTest:
    chosen = settings()
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(
        model=connect_model(chosen, transport=transport(failure), sleep=lambda _: None),
        tuning=tuning_from(chosen),
        book=CountingBook(),  # type: ignore[arg-type]
        assets=BUILT_IN_ASSETS,
        clock=lambda: INVENTED_NOW,
        zone=INVENTED_ZONE,
        settings=chosen,
        places=DataPlaces(data),
        ledger=FakeLedger(),
        ledger_kind=LedgerKind.DEMO,
    )
    return page.run()


@pytest.mark.parametrize("failure", list(FAILURES))
def test_no_page_and_no_record_shows_it(
    failure: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    page = send(page_with(failure, data), "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT")
    record_page = every_text(page)
    page = page.switch_page("assistant_page.py").run()
    page = say_on_page(page, "我现在持有哪些币？")
    assistant_page = every_text(page)
    page = page.switch_page("settings_page.py").run()

    assert "Nothing was sent to the local model instead." in record_page
    assert "Nothing was sent to the local model instead." in assistant_page
    for shown in (record_page, assistant_page, every_text(page)):
        assert_none_in(shown)
    written = DataPlaces(data).assistant_record.read_text(encoding="utf-8")
    assert written
    assert_none_in(written)
    printed = capsys.readouterr()
    assert_none_in(printed.out + printed.err)
    assert not page.exception


@pytest.mark.parametrize("failure", list(FAILURES))
def test_the_try_out_script_does_not_show_it(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def connect(chosen: ModelSettings) -> CloudModel:
        return CloudModel(chosen, transport=transport(failure))

    monkeypatch.setattr(try_assistant, "connect_model", connect)
    out = io.StringIO()

    try_assistant.main(["我现在持有哪些币？"], out=out)

    assert "failure: ModelError" in out.getvalue()
    assert_none_in(out.getvalue())


@pytest.mark.parametrize("failure", list(FAILURES))
def test_an_experiments_results_file_does_not_hold_it(
    failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def connect(chosen: ModelSettings) -> CloudModel:
        return CloudModel(chosen, transport=transport(failure))

    monkeypatch.setattr(runner, "connect_model", connect)
    out = io.StringIO()

    assert runner.main(["--only", "d01"], out=out, results_dir=tmp_path) == 0
    (path,) = tmp_path.glob("*.jsonl")
    _, sentence, *_ = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    assert sentence["failure"]["kind"] in {
        "unreachable",
        "timed_out",
        "server_error",
        "rate_limited",
        "model_not_found",
    }
    for written in (path.read_text("utf-8"), out.getvalue()):
        assert_none_in(written)
