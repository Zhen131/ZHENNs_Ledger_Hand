"""Tests of the pages with a cloud plug: the line at the top, the failures, the record, the ledger.

With the cloud or the deepseek plug, the Assistant and Record pages keep a
line at the top that says what is sent where; with the local plug there is
none. Each way a cloud service fails is said in its own sentence on both
pages, and nothing is then sent to the local model instead. The settings
page switches to DeepSeek and back; a setting that does not fit, or a key
that is missing, is said in one sentence on every page. The record on this
machine says where the model was asked, and the ledger is told the model's
own name. Every value is invented; nothing reaches the network.
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Sequence
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.flows.assistant_record import RecordRead, read_record
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ledger.link_ledger import LinkLedger
from ledger_hand.ports import (
    LedgerError,
    Message,
    ModelError,
    ModelErrorKind,
    ModelReply,
    Picture,
    ToolReply,
)
from ledger_hand.settings import DataPlaces, ModelSettings, Plug, Secret, Variable
from ledger_hand.ui.cloud_notice import ASSISTANT_NOTICE_KEY, RECORD_NOTICE_KEY
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.ui.settings_form import NOTE_KEY
from ledger_hand.ui.settings_page import PLUG_KEY
from ledger_hand.wiring import Parts, assemble
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.ledger.test_link_ledger import SampleLink, facts, sample
from tests.llm.fake_deepseek import deepseek_settings
from tests.llm.local_requests import GOLDEN, NOW, ZONE
from tests.ui.app_harness import APP_FILE, program_said, send
from tests.ui.assistant_harness import CountingBook, open_assistant, replies, say_on_page
from tests.ui.page_harness import (
    Builds,
    apply,
    every_text,
    note,
    open_built,
    set_setting,
    to_record,
    to_settings,
)
from tests.ui.screenshot_harness import PNG

KEY = "sk-invented-deepseek-0123456789abcdef"
GENERAL = "sk-invented-general-pages-0123456789"
CLOUD = ModelSettings(
    plug=Plug.CLOUD,
    base_url="https://api.example.com/v1",
    model="invented-cloud-model",
    api_key=Secret(GENERAL),
)
DEEPSEEK = deepseek_settings()
PASSAGE = "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT"


class NoLocalModel:
    """Stands for the local plug: any call to it fails the test."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: Sequence[Message], **_: object) -> ModelReply:
        self.calls += 1
        raise AssertionError("the local model was asked")

    def chat_with_pictures(
        self, messages: Sequence[Message], pictures: Sequence[Picture], **_: object
    ) -> ModelReply:
        self.calls += 1
        raise AssertionError("the local model was asked")


def parts_for(settings: ModelSettings, model: object, data: Path, local: NoLocalModel) -> Parts:
    return Parts(
        model=model,  # type: ignore[arg-type]
        tuning=tuning_from(settings),
        book=CountingBook(),  # type: ignore[arg-type]
        assets=BUILT_IN_ASSETS,
        clock=lambda: INVENTED_NOW,
        zone=INVENTED_ZONE,
        settings=settings,
        places=DataPlaces(data),
        vision_model=local,  # type: ignore[arg-type]
        ledger=FakeLedger(),
        ledger_kind=LedgerKind.DEMO,
    )


def opened(settings: ModelSettings, model: object, data: Path, local: NoLocalModel) -> AppTest:
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = parts_for(settings, model, data, local)
    return page.run()


def notice(page: AppTest, key: str) -> list[str]:
    try:
        return [str(w.value) for w in page.container(key=key).warning]
    except KeyError:
        return []


# --- S12: the line at the top ------------------------------------------------------------


@pytest.mark.parametrize("settings", [DEEPSEEK, CLOUD], ids=["deepseek", "cloud"])
def test_both_pages_keep_a_line_saying_what_is_sent_where(
    settings: ModelSettings, tmp_path: Path
) -> None:
    page = opened(settings, RoutedModel(), tmp_path / "data", NoLocalModel())

    (record,) = notice(page, RECORD_NOTICE_KEY)
    page = page.switch_page("assistant_page.py").run()
    (assistant,) = notice(page, ASSISTANT_NOTICE_KEY)

    assert record.endswith(f"Every passage you type here is sent to {settings.base_url}.")
    assert settings.model in record
    assert assistant.endswith(
        "Everything you say here, and what the assistant looks up in your ledger (holdings, "
        f"trades, cash balances), is sent to {settings.base_url}."
    )
    assert not page.exception


def test_the_deepseek_line_names_the_service_its_address_and_model(tmp_path: Path) -> None:
    page = opened(DEEPSEEK, RoutedModel(), tmp_path / "data", NoLocalModel())

    (record,) = notice(page, RECORD_NOTICE_KEY)

    assert record.startswith("Model: DeepSeek (https://api.deepseek.com), deepseek-v4-pro.")


def test_the_local_plug_has_no_such_line_on_either_page(tmp_path: Path) -> None:
    page = opened(ModelSettings(), RoutedModel(), tmp_path / "data", NoLocalModel())

    assert notice(page, RECORD_NOTICE_KEY) == []
    page = page.switch_page("assistant_page.py").run()
    assert notice(page, ASSISTANT_NOTICE_KEY) == []


# --- S11: each failure said on both pages, and nothing sent to the local model ----------

FAILURES = {
    "unreachable": ModelError(ModelErrorKind.UNREACHABLE, "invented: no answer"),
    "timed out": ModelError(ModelErrorKind.TIMED_OUT, "invented: too slow"),
    "no money": ModelError(ModelErrorKind.SERVER_ERROR, "refused", status=402),
    "key 401": ModelError(ModelErrorKind.SERVER_ERROR, "refused", status=401),
    "key 403": ModelError(ModelErrorKind.SERVER_ERROR, "refused", status=403),
    "too often, a wait": ModelError(
        ModelErrorKind.RATE_LIMITED, "too often", status=429, retry_after_seconds=2.5
    ),
    "too often": ModelError(ModelErrorKind.RATE_LIMITED, "too often", status=429),
    "no such model": ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no model", status=400),
}


def expected(name: str, settings: ModelSettings) -> list[str]:
    """Words each failure's sentence must hold, with the settings' own values."""
    key = "DEEPSEEK_API_KEY" if settings.plug is Plug.DEEPSEEK else "LEDGER_HAND_MODEL_KEY"
    return {
        "unreachable": ["this machine can reach the internet", settings.base_url],
        "timed out": ["No whole reply came from", "allow more time"],
        "no money": ["no money left on it (status 402)", "LEDGER_HAND_MODEL_PLUG to local"],
        "key 401": [f"Check {key} in the environment", "(status 401)"],
        "key 403": [f"Check {key} in the environment", "(status 403)"],
        "too often, a wait": ["asked to wait 3 seconds"],
        "too often": ["called too often. Wait a little"],
        "no such model": [f"has no model named {settings.model}", "list of models"],
    }[name]


@pytest.mark.parametrize("name", list(FAILURES))
@pytest.mark.parametrize("settings", [DEEPSEEK, CLOUD], ids=["deepseek", "cloud"])
def test_each_failure_is_said_on_the_record_page(
    settings: ModelSettings, name: str, tmp_path: Path
) -> None:
    local = NoLocalModel()
    page = opened(settings, RoutedModel(screen=[FAILURES[name]]), tmp_path / "data", local)

    page = send(page, PASSAGE)

    (said,) = program_said(page)
    for words in expected(name, settings):
        assert words in said, (words, said)
    assert "Nothing was sent to the local model instead." in said
    assert "Ollama" not in said and "load it into memory" not in said
    assert local.calls == 0
    assert not page.exception


@pytest.mark.parametrize("name", list(FAILURES))
@pytest.mark.parametrize("settings", [DEEPSEEK, CLOUD], ids=["deepseek", "cloud"])
def test_each_failure_is_said_on_the_assistant_page(
    settings: ModelSettings, name: str, tmp_path: Path
) -> None:
    local = NoLocalModel()
    model = RoutedModel(tools=[FAILURES[name]])
    page = opened(settings, model, tmp_path / "data", local)
    page = page.switch_page("assistant_page.py").run()

    page = say_on_page(page, "我现在持有哪些币？")

    said = every_text(page)
    for words in expected(name, settings):
        assert words in said, (words, said)
    assert "Nothing was sent to the local model instead." in said
    assert local.calls == 0
    assert len(model.tools.calls) == 1
    assert not page.exception


# --- S14: the record says where the model was asked ---------------------------------------


def test_the_record_says_the_plug_the_service_the_address_and_the_model(tmp_path: Path) -> None:
    data = tmp_path / "data"
    answered = ToolReply(text="Invented answer.", calls=(), record=scripted_record())
    page = opened(DEEPSEEK, RoutedModel(tools=[answered]), data, NoLocalModel())
    page = page.switch_page("assistant_page.py").run()

    say_on_page(page, "我现在持有哪些币？")

    read = read_record(DataPlaces(data).assistant_record)
    assert isinstance(read, RecordRead)
    (entry,) = read.entries
    assert entry["models"] == {
        "tools": "deepseek-v4-pro",
        "vision": None,
        "plug": "deepseek",
        "service": "DeepSeek",
        "address": "https://api.deepseek.com",
    }
    written = DataPlaces(data).assistant_record.read_text(encoding="utf-8")
    assert KEY not in written and KEY[-4:] not in written


# --- S15: a screenshot is not sent anywhere -------------------------------------------------


def test_a_screenshot_with_deepseek_is_turned_down_on_both_pages(tmp_path: Path) -> None:
    local = NoLocalModel()
    page = opened(DEEPSEEK, RoutedModel(), tmp_path / "data", local)

    page = (
        page.file_uploader(key="screenshot_upload_0")
        .set_value(("order.png", PNG, "image/png"))
        .run()
    )
    shown = every_text(page)
    page = page.switch_page("assistant_page.py").run()
    page = (
        page.file_uploader(key="assistant_screenshot_upload_0")
        .set_value(("order.png", PNG, "image/png"))
        .run()
    )
    shown_too = every_text(page)

    for text in (shown, shown_too):
        assert "LEDGER_HAND_MODEL_PLUG is deepseek, so nothing was sent anywhere" in text
    assert local.calls == 0


def test_the_assistant_page_with_deepseek_runs_the_tools_and_its_input_is_open() -> None:
    answered = ToolReply(text="你持有 BTC。", calls=(), record=scripted_record())
    model = RoutedModel(tools=[answered])

    page = open_assistant(model, ledger=FakeLedger(), settings=DEEPSEEK)
    page = say_on_page(page, "我现在持有哪些币？")

    assert replies(page, 1)[0] == "你持有 BTC。"
    assert len(model.tools.calls) == 1
    assert not page.exception


# --- S3, S5, S6: through the real wiring -----------------------------------------------------


@pytest.fixture
def deepseek_key(bare_machine: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(Variable.DEEPSEEK_KEY.value, KEY)
    return bare_machine


def plug_line(page: AppTest) -> str:
    (line,) = page.container(key=PLUG_KEY).text
    return str(line.value)


def test_switching_to_deepseek_and_back_on_the_settings_page(deepseek_key: Path) -> None:
    builds = Builds(RoutedModel())
    page = to_settings(open_built(builds))

    page = apply(set_setting(page, Variable.PLUG, "deepseek"))
    on_deepseek = page.session_state[PARTS_KEY].settings
    line = plug_line(page)
    page = apply(set_setting(page, Variable.PLUG, "local"))
    back = page.session_state[PARTS_KEY].settings

    assert (on_deepseek.base_url, on_deepseek.model) == (
        "https://api.deepseek.com",
        "deepseek-v4-pro",
    )
    assert line == (
        "Model plug now: deepseek, DeepSeek's chat endpoint at https://api.deepseek.com; what "
        "is typed is sent there. Model: deepseek-v4-pro. Key: DEEPSEEK_API_KEY set."
    )
    assert back == dataclasses.replace(ModelSettings(), deepseek_key=Secret(KEY))
    assert plug_line(page) == (
        "Model plug now: local, Ollama's own chat endpoint at http://127.0.0.1:11434. Key: not set."
    )
    assert KEY not in every_text(page)
    assert not page.exception


def test_after_switching_back_the_local_model_is_sent_what_it_was_before(
    deepseek_key: Path,
) -> None:
    import json

    from ledger_hand.extraction.extractor import extract
    from ledger_hand.llm.connect import connect_model
    from tests.llm.fake_server import mock_transport

    builds = Builds(RoutedModel())
    page = to_settings(open_built(builds))
    page = apply(set_setting(page, Variable.PLUG, "deepseek"))
    page = apply(set_setting(page, Variable.PLUG, "local"))
    settings = page.session_state[PARTS_KEY].settings
    seen: list[dict[str, object]] = []

    def answer(request: object) -> object:
        import httpx

        assert isinstance(request, httpx.Request)
        seen.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers.items()),
                "body": request.content.decode("utf-8"),
            }
        )
        return httpx.Response(400, content=b'{"error": "invented refusal"}')

    model = connect_model(settings, transport=mock_transport(answer), sleep=lambda _: None)  # type: ignore[arg-type]
    extract("昨天买了 0.5 个 BTC，单价 60000 美元", model, now=NOW, zone=ZONE)

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert seen == golden["requests"][:1]


def test_another_address_stops_the_plug_but_the_settings_page_opens_and_says_why(
    deepseek_key: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "deepseek")
    monkeypatch.setenv(Variable.URL.value, "https://api.example.com/v1")

    page = to_settings(open_built(Builds(RoutedModel())))

    (shown,) = [str(error.value) for error in page.error]
    assert "LEDGER_HAND_MODEL_URL" in shown
    assert "DeepSeek's address is fixed" in shown
    assert not page.exception


def test_a_switch_to_another_address_on_the_page_is_refused(deepseek_key: Path) -> None:
    page = to_settings(open_built(Builds(RoutedModel())))
    page = set_setting(page, Variable.PLUG, "deepseek")
    page = apply(set_setting(page, Variable.URL, "https://api.example.com/v1"))

    found = note(page, NOTE_KEY)
    assert found is not None
    assert found[1].startswith("Not applied: LEDGER_HAND_MODEL_URL: ")
    assert page.session_state[PARTS_KEY].settings.plug is Plug.LOCAL


@pytest.mark.parametrize("where", ["record", "assistant", "settings"])
def test_without_its_key_every_page_says_so_in_one_sentence(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "deepseek")
    monkeypatch.setenv(Variable.KEY.value, GENERAL)
    builds = Builds(RoutedModel())

    page = open_built(builds)
    if where == "assistant":
        page = page.switch_page("assistant_page.py").run()
    if where == "settings":
        page = to_settings(page)
    else:
        page = to_record(page) if where == "record" else page

    (error,) = [str(shown.value) for shown in page.error]
    assert "DEEPSEEK_API_KEY" in error
    assert GENERAL not in every_text(page)
    assert builds.built == []
    assert not page.exception


# --- S13: the ledger is told the model's own name -------------------------------------------


def test_the_ledger_is_told_deepseeks_model_for_each_proposal(
    deepseek_key: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "deepseek")
    name = assemble().settings.model
    link = SampleLink(
        ("list_assets", sample("list-assets")),
        ("propose_trade_add", sample("propose-add-one-refused")),
        ("list_trades", sample("list-trades-no-filter")),
        ("list_assets", sample("list-assets")),
        ("propose_trade_update", sample("propose-update-fee-only")),
        ("propose_trade_delete", sample("propose-update-fee-only")),
    )
    ledger = LinkLedger(link, model_name=name, today=lambda: INVENTED_NOW.date())

    # Only what is sent counts here; how the ledger's sample answers fit is not the point.
    with contextlib.suppress(LedgerError):
        ledger.propose_add((facts(),), "买了")
    (listed, *_) = ledger.list_trades(TradeFilter()).trades
    with contextlib.suppress(LedgerError):
        ledger.propose_update(listed.id, listed.facts, "改一下")
    with contextlib.suppress(LedgerError):
        ledger.propose_delete(listed.id, "删掉")

    sent = [arguments for tool, arguments in link.asked if tool.startswith("propose_")]
    assert name == "deepseek-v4-pro"
    assert [arguments["modelName"] for arguments in sent] == ["deepseek-v4-pro"] * 3
