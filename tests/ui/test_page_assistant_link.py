"""Tests of the assistant page reaching the ledger page: the block at the top, the cards, the token.

The page runs headless. The assistant link is a stand-in (``FakeLink``)
kept by a real ``LinkKeeper``, put where the page finds a test's own
keeper; the ledger behind it is the demo book (``FakeLedger``) wrapped to
count every question about a proposal. Nothing reaches the network or
Node.js. The token is one fixed invented string, looked for afterwards in
everything the page drew, kept or wrote.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.proposals import ProposalState, ProposalStatus
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ledger.link_client import PageState
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ledger.link_keeper import LinkKeeper, LinkState
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort, ModelPort
from ledger_hand.settings import (
    LEDGER_DIRECTORY_VARIABLE,
    AssistantLedger,
    DataPlaces,
    ModelSettings,
)
from ledger_hand.ui.assistant_cards import (
    REFRESH_KEY,
    check_key,
    reject_key,
    save_key,
)
from ledger_hand.ui.assistant_ledger import KEEPER_KEY
from ledger_hand.ui.assistant_link_panel import (
    CHOICE_KEY,
    HIDE_TOKEN_KEY,
    PANEL_KEY,
    SHOW_TOKEN_KEY,
    START_KEY,
    STATE_KEY,
    STOP_KEY,
    TOKEN_KEY,
)
from ledger_hand.ui.assistant_link_words import START_FAILURES, STATE_WORDS
from ledger_hand.ui.assistant_tables import IN_THE_LEDGER
from ledger_hand.ui.assistant_view import table_key
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.wiring import LinkNotSet, NoLink, Parts
from tests.fakes.routed_model import RoutedModel
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.test_conversation import RECORD, SPOT
from tests.flows.test_ledger_answers import PARTLY, PARTLY_ROWS
from tests.ui.app_harness import APP_FILE
from tests.ui.assistant_harness import (
    INPUT_KEY,
    CountingBook,
    card_text,
    rows_of,
    say_on_page,
    texts_of,
    to_assistant,
)
from tests.ui.test_page_assistant import ONE_BUY, TWO_BUYS, one_buy_model, two_buys_model

# An invented token, the same in every test, so that it can be looked for.
TOKEN = "InventedPageTestToken_0123456789abcdefXYZ"
LEDGER_LINE_KEY = "assistant_ledger_line"


class FakeLink:
    """Stands in for the ledger's assistant link: started or not, and what the page did."""

    def __init__(self, failure: LinkFailure | None = None) -> None:
        self.failure = failure
        self.page = PageState.CONNECTED
        self.alive = False
        self.port = 47668
        self.page_port = 3068

    def start(self) -> None:
        if self.failure is not None:
            raise LedgerLinkError(self.failure, "seen while starting")
        self.alive = True

    def running(self) -> bool:
        return self.alive

    def page_state(self) -> PageState:
        return self.page

    def close(self) -> None:
        self.alive = False

    def token_to_show(self) -> str:
        return TOKEN


class CountingLedger:
    """The demo ledger, counting every question about where a proposal stands."""

    def __init__(self, inner: FakeLedger) -> None:
        self.inner = inner
        self.asked: list[str] = []
        self.answer: Callable[[str], ProposalState] | None = None

    def proposal_status(self, proposal_id: str) -> ProposalState:
        self.asked.append(proposal_id)
        if self.answer is not None:
            return self.answer(proposal_id)
        return self.inner.proposal_status(proposal_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


class Fixture:
    """One keeper over one stand-in link, with the counting ledger as its plug."""

    def __init__(self, failure: LinkFailure | None = None) -> None:
        self.links: list[FakeLink] = []
        self.ledger = CountingLedger(usdt_only_ledger())
        self.failure = failure
        self.keeper = LinkKeeper(self._link, self._plug)  # type: ignore[arg-type]

    def _link(self) -> FakeLink:
        self.links.append(FakeLink(self.failure))
        return self.links[-1]

    def _plug(self, _caller: object, _model: str) -> LedgerPort:
        return self.ledger  # type: ignore[return-value]

    @property
    def link(self) -> FakeLink:
        return self.links[-1]


def open_page(
    model: ModelPort,
    fixture: Fixture | NoLink,
    *,
    first: AssistantLedger = AssistantLedger.PAGE,
    places: DataPlaces | None = None,
    vision: ModelPort | None = None,
) -> AppTest:
    """The app run once with a demo ledger, this keeper and ``first`` as the first ledger."""
    settings = ModelSettings()
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(
        model=model,
        tuning=tuning_from(settings),
        book=CountingBook(),  # type: ignore[arg-type]
        assets=BUILT_IN_ASSETS,
        clock=lambda: INVENTED_NOW,
        zone=INVENTED_ZONE,
        settings=settings,
        places=places,
        vision_model=vision,
        ledger=usdt_only_ledger(),
        ledger_kind=LedgerKind.DEMO,
        first_ledger=first,
    )
    page.session_state[KEEPER_KEY] = fixture.keeper if isinstance(fixture, Fixture) else fixture
    page.run()
    return to_assistant(page)


def started(model: ModelPort, fixture: Fixture, **given: Any) -> AppTest:
    page = open_page(model, fixture, **given)
    return page.button(key=START_KEY).click().run()


def state_line(page: AppTest) -> str:
    (line,) = texts_of(page, STATE_KEY)
    return line


def everything_drawn(page: AppTest) -> str:
    """Every text, caption, box, code block and input value the page holds now, and its state."""
    found: list[str] = []
    for kind in (
        "text",
        "caption",
        "code",
        "markdown",
        "info",
        "warning",
        "error",
        "success",
        "exception",
        "subheader",
        "button",
        "radio",
        "chat_input",
        "text_area",
        "text_input",
    ):
        for element in page.get(kind):
            found.append(str(getattr(element, "value", "")))
            found.append(str(getattr(element, "label", "")))
            found.append(str(element.proto))
    found.append(kept_state(page))
    return "\n".join(found)


def kept_state(page: AppTest) -> str:
    """Everything kept in the tab's session, written out."""
    kept = page.session_state.to_dict()
    return "\n".join(f"{key}={value!r}" for key, value in kept.items())


@pytest.fixture(autouse=True)
def _no_ledger_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test here reaches the shared keeper the wiring would build."""
    monkeypatch.delenv(LEDGER_DIRECTORY_VARIABLE, raising=False)


# --- the choice -----------------------------------------------------------------


def test_the_demo_ledger_is_reached_first_and_the_ledger_page_block_is_not_drawn() -> None:
    page = open_page(RoutedModel(), Fixture(), first=AssistantLedger.DEMO)

    assert page.radio(key=CHOICE_KEY).value is AssistantLedger.DEMO
    assert "demo ledger" in str(page.container(key=LEDGER_LINE_KEY).caption[0].value)
    assert [b.key for b in page.button if b.key in (START_KEY, STOP_KEY)] == []


def test_switching_clears_the_chat_and_the_page_line_cannot_be_taken_for_the_demo() -> None:
    fixture = Fixture()
    page = open_page(one_buy_model(), fixture, first=AssistantLedger.DEMO)
    page = say_on_page(page, ONE_BUY)
    assert len(page.chat_message) == 2

    page = page.radio(key=CHOICE_KEY).set_value(AssistantLedger.PAGE).run()

    (note,) = [str(m.text[0].value) for m in page.chat_message]
    assert note.startswith("Switched to your ledger page. This chat was cleared")
    (line,) = page.container(key=LEDGER_LINE_KEY).info
    assert "your ledger page" in str(line.value)
    assert "your real ledger" in str(line.value)
    assert page.container(key=LEDGER_LINE_KEY).caption == []


def test_the_choice_lasts_while_another_page_is_shown() -> None:
    from tests.ui.page_harness import to_record

    page = open_page(RoutedModel(), Fixture(), first=AssistantLedger.DEMO)
    page = page.radio(key=CHOICE_KEY).set_value(AssistantLedger.PAGE).run()

    page = to_assistant(to_record(page))

    assert page.radio(key=CHOICE_KEY).value is AssistantLedger.PAGE
    assert len(page.chat_message) == 1


def test_without_the_ledgers_folder_the_block_says_what_to_set_and_nothing_is_sent() -> None:
    page = open_page(RoutedModel(), NoLink(LinkNotSet.NO_FOLDER))

    (warning,) = page.container(key=PANEL_KEY).warning
    assert f"set {LEDGER_DIRECTORY_VARIABLE}" in str(warning.value)
    assert page.chat_input(key=INPUT_KEY).proto.disabled
    assert page.exception == []


# --- starting, the five states, stopping -------------------------------------------


def test_before_start_the_block_says_not_started_and_shows_no_port() -> None:
    page = open_page(RoutedModel(), Fixture())

    assert state_line(page) == f"Assistant link: {STATE_WORDS[LinkState.NOT_STARTED]}"
    assert not page.button(key=START_KEY).disabled
    assert page.button(key=STOP_KEY).disabled
    assert not any("Port:" in str(t.value) for t in page.text)


def test_after_start_waiting_the_block_shows_the_port_and_the_three_steps() -> None:
    fixture = Fixture()
    fixture_page = open_page(RoutedModel(), fixture)
    fixture.keeper.start()
    fixture.link.page = PageState.NOT_CONNECTED
    page = fixture_page.run()

    assert state_line(page) == f"Assistant link: {STATE_WORDS[LinkState.WAITING]}"
    texts = [str(t.value) for t in page.container(key=PANEL_KEY).text]
    assert "Port: 47668" in texts
    steps = next(t for t in texts if t.startswith("1. "))
    assert "http://127.0.0.1:3068" in steps
    assert 'Press "Connect assistant"' in steps
    assert "Enter port 47668 and paste the token" in steps


@pytest.mark.parametrize(
    ("page_state", "killed", "state"),
    [
        (PageState.NOT_CONNECTED, "", LinkState.WAITING),
        (PageState.CONNECTED, "", LinkState.CONNECTED),
        (PageState.DISCONNECTED, "", LinkState.DISCONNECTED),
        (PageState.CONNECTED, "killed", LinkState.GONE),
    ],
)
def test_each_state_of_a_started_link_is_said(
    page_state: PageState, killed: str, state: LinkState
) -> None:
    fixture = Fixture()
    page = started(RoutedModel(), fixture)
    fixture.link.page = page_state
    fixture.link.alive = not killed

    page = page.run()

    assert state_line(page) == f"Assistant link: {STATE_WORDS[state]}"
    assert page.exception == []


def test_a_stop_in_one_tab_is_seen_in_another_and_a_new_start_makes_a_new_link() -> None:
    fixture = Fixture()
    one = started(RoutedModel(), fixture)
    other = open_page(RoutedModel(), fixture)
    assert state_line(other) == f"Assistant link: {STATE_WORDS[LinkState.CONNECTED]}"

    one = one.button(key=STOP_KEY).click().run()
    other = other.run()

    assert state_line(other) == f"Assistant link: {STATE_WORDS[LinkState.STOPPED]}"
    assert "every tab" in state_line(other)
    other = other.button(key=START_KEY).click().run()
    assert len(fixture.links) == 2


@pytest.mark.parametrize("failure", list(LinkFailure))
def test_every_failed_start_is_said_in_a_plain_sentence_with_no_traceback(
    failure: LinkFailure,
) -> None:
    page = started(RoutedModel(), Fixture(failure))

    (warning,) = page.container(key=PANEL_KEY).warning
    assert str(warning.value).startswith(START_FAILURES[failure])
    assert page.exception == []
    assert state_line(page) == f"Assistant link: {STATE_WORDS[LinkState.NOT_STARTED]}"


def test_a_ledger_folder_without_its_packages_says_to_run_npm_install() -> None:
    page = started(RoutedModel(), Fixture(LinkFailure.PACKAGES_MISSING))

    (warning,) = page.container(key=PANEL_KEY).warning
    assert "Run npm install in the ledger's folder" in str(warning.value)


def test_a_link_killed_in_the_middle_is_said_and_typing_asks_no_model() -> None:
    fixture = Fixture()
    model = one_buy_model()
    page = started(model, fixture)
    fixture.link.alive = False

    page = say_on_page(page, ONE_BUY)

    assert state_line(page) == f"Assistant link: {STATE_WORDS[LinkState.GONE]}"
    assert model.tools.steps_left == 1
    assert page.exception == []


# --- not connected: no model is asked -------------------------------------------


@pytest.mark.parametrize("page_state", [PageState.NOT_CONNECTED, PageState.DISCONNECTED])
def test_typing_while_the_page_is_not_connected_asks_no_model_and_says_how(
    page_state: PageState,
) -> None:
    fixture = Fixture()
    model = one_buy_model()
    page = started(model, fixture)
    fixture.link.page = page_state

    page = say_on_page(page, ONE_BUY)

    assert model.tools.steps_left == 1
    assert model.screen.steps_left == 1
    assert fixture.ledger.asked == []
    (error,) = page.chat_message[1].error
    assert str(error.value).startswith("Your ledger page is not connected yet")
    assert "Enter port 47668" in str(error.value)


def test_typing_before_start_says_to_press_start() -> None:
    model = one_buy_model()
    page = say_on_page(open_page(model, Fixture()), ONE_BUY)

    (error,) = page.chat_message[1].error
    assert "Press Start at the top of this page first" in str(error.value)
    assert model.tools.steps_left == 1


def test_the_screenshot_area_is_greyed_out_while_the_page_is_not_connected() -> None:
    fixture = Fixture()
    page = started(RoutedModel(), fixture, vision=RoutedModel())
    assert not any(box.proto.disabled for box in page.file_uploader)
    fixture.link.page = PageState.NOT_CONNECTED

    page = page.run()

    uploads = list(page.file_uploader)
    assert uploads
    assert all(box.proto.disabled for box in uploads)


# --- the token ------------------------------------------------------------------


def test_the_token_is_drawn_nowhere_until_show_token_and_nowhere_after_hide() -> None:
    fixture = Fixture()
    page = started(RoutedModel(), fixture)
    fixture.link.page = PageState.NOT_CONNECTED
    page = page.run()

    assert TOKEN not in everything_drawn(page)
    page = page.button(key=SHOW_TOKEN_KEY).click().run()
    (code,) = page.container(key=TOKEN_KEY).code
    assert code.value == TOKEN
    assert TOKEN not in kept_state(page)
    page = page.button(key=HIDE_TOKEN_KEY).click().run()
    assert TOKEN not in everything_drawn(page)


def test_the_token_reaches_no_chat_no_record_and_no_model(tmp_path: Path) -> None:
    fixture = Fixture()
    model = one_buy_model()
    page = started(model, fixture, places=DataPlaces(tmp_path))
    fixture.link.page = PageState.NOT_CONNECTED
    page = page.run().button(key=SHOW_TOKEN_KEY).click().run()
    fixture.link.page = PageState.CONNECTED

    page = say_on_page(page, ONE_BUY)

    record = (tmp_path / "assistant-record.jsonl").read_text(encoding="utf-8")
    assert '"ledger": "page"' in record
    assert TOKEN not in record
    assert "47668" not in record
    assert all(TOKEN not in "\n".join(str(t.value) for t in m.text) for m in page.chat_message)
    handed = [model.tools.calls, model.screen.calls, model.extraction.calls]
    assert model.tools.calls
    assert TOKEN not in repr(handed)


# --- the cards ------------------------------------------------------------------


def sent_once(fixture: Fixture) -> tuple[AppTest, str]:
    page = say_on_page(started(one_buy_model(), fixture), ONE_BUY)
    (proposal,) = [
        f"proposal-{n}" for n in range(1, 10) if _pending(fixture.ledger.inner, f"proposal-{n}")
    ]
    return page, proposal


def _pending(ledger: FakeLedger, proposal: str) -> bool:
    try:
        return ledger.proposal_status(proposal).status is ProposalStatus.PENDING
    except LedgerError:
        return False


def test_a_card_says_it_was_sent_to_the_page_and_drawing_again_asks_nothing() -> None:
    fixture = Fixture()
    page, proposal = sent_once(fixture)

    for _ in range(10):
        page = page.run()

    assert fixture.ledger.asked == []
    lines = card_text(page, proposal)
    assert (
        "Status: sent, waiting for you to press Save on your ledger page (not checked yet)" in lines
    )
    assert [b.key for b in page.button if b.key in (REFRESH_KEY,)] == []
    assert [b.key for b in page.button if b.key in (save_key(proposal), reject_key(proposal))] == []
    assert "Sent to the pending list on your ledger page" in "\n".join(
        str(c.value) for c in page.caption
    )


def check(page: AppTest, proposal: str) -> AppTest:
    return page.button(key=check_key(proposal)).click().run()


def _state(status: ProposalStatus, **given: Any) -> Callable[[str], ProposalState]:
    return lambda proposal: ProposalState(proposal_id=proposal, status=status, **given)


def _fails(kind: LedgerErrorKind, code: str, message: str) -> Callable[[str], ProposalState]:
    def answer(_proposal: str) -> ProposalState:
        raise LedgerError(kind, code, message)

    return answer


@pytest.mark.parametrize(
    ("answer", "said"),
    [
        (_state(ProposalStatus.PENDING), "still waiting in the pending list on your ledger page"),
        (
            _state(ProposalStatus.SAVED, trade_id="trade-77"),
            "saved in your ledger, as trade trade-77",
        ),
        (_state(ProposalStatus.REJECTED), "rejected on your ledger page"),
        (
            _state(ProposalStatus.VOID, reason="TRADE_CHANGED", message="那一笔已经变了"),
            "void: it can no longer be saved (那一笔已经变了)",
        ),
        (
            _state(ProposalStatus.VOID, reason="ASSISTANT_DISCONNECTED", message="助手已断开"),
            "void because your ledger page disconnected from the assistant, not because you "
            "rejected it",
        ),
        (
            _fails(LedgerErrorKind.UNREACHABLE, "LEDGER_PAGE_NOT_CONNECTED", "not connected"),
            "could not be asked: your ledger page is not connected. Connect it first",
        ),
        (
            _fails(LedgerErrorKind.RESULT_UNKNOWN, "PROPOSAL_NOT_FOUND", "not found"),
            "The ledger page may have been reloaded, so the result of this one can no longer "
            "be looked up",
        ),
        (
            _fails(LedgerErrorKind.TIMED_OUT, "LEDGER_PAGE_TIMEOUT", "no answer"),
            "did not answer in time",
        ),
    ],
)
def test_check_with_the_ledger_asks_once_keeps_and_says_each_of_the_seven_results(
    answer: Callable[[str], ProposalState], said: str
) -> None:
    fixture = Fixture()
    page, proposal = sent_once(fixture)
    fixture.ledger.answer = answer

    page = check(page, proposal)
    page = page.run().run()

    assert fixture.ledger.asked == [proposal]
    assert any(said in line for line in card_text(page, proposal)), card_text(page, proposal)


def test_a_card_of_two_trades_asks_both_on_one_check() -> None:
    fixture = Fixture()
    page = say_on_page(started(two_buys_model(), fixture), TWO_BUYS)
    waiting = [
        f"proposal-{n}" for n in range(1, 10) if _pending(fixture.ledger.inner, f"proposal-{n}")
    ]
    assert len(waiting) == 2

    page = check(page, waiting[0])

    assert fixture.ledger.asked == waiting


# --- the table of a proposal partly taken (68B3, addition 1) ---------------------


def test_the_table_marks_which_trade_waits_and_which_was_not_taken() -> None:
    model = RoutedModel(tools=[RECORD], screen=[SPOT], extraction=[PARTLY_ROWS])

    page = say_on_page(open_page(model, Fixture(), first=AssistantLedger.DEMO), PARTLY)

    first, second = rows_of(page, table_key(1, "proposed"))
    assert first[IN_THE_LEDGER] == "waiting for you to confirm (proposal-1)"
    assert second[IN_THE_LEDGER].startswith("not taken: With this, a sell")


def test_a_proposal_taken_whole_keeps_the_table_as_it_was() -> None:
    page = say_on_page(open_page(one_buy_model(), Fixture(), first=AssistantLedger.DEMO), ONE_BUY)

    (row,) = rows_of(page, table_key(1, "proposed"))
    assert IN_THE_LEDGER not in row
