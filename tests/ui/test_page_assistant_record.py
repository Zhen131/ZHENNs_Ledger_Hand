"""Tests of the assistant's record as the pages show it, with the data folder in a temporary folder.

- Three things said on the Assistant page make three entries, each read
  back; a screenshot's entry holds none of the picture's bytes.
- A folder that cannot be written: the proposal is still sent, and a
  warning under the reply says it was not kept.
- Parts without a data folder: nothing is written, and the page says there
  is no record this time.
- A record of a newer version, or with a line that cannot be read: not one
  byte changes, the thing said is still done and the page says it was not
  kept, and the Settings page says the record cannot be read and why.
- A last line cut off half-way: the Settings page counts the whole lines,
  and the next thing said leaves a whole file.
- The Settings page shows where the file is, that it is plain text with the
  words said, and how many entries; clearing takes two presses, and a file
  that cannot be read can be cleared too.
- A refused step limit greys the Assistant page's screenshot out too, and
  the vision model is not asked.

Every sentence and picture is invented.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.errors import AppTestError

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.flows.assistant_record import RECORD_VERSION, RecordRead, read_record
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ModelPort, ToolCall, ToolReply
from ledger_hand.settings import DataPlaces, ModelSettings
from ledger_hand.ui.assistant_record_words import NO_RECORD, PLAIN_TEXT
from ledger_hand.ui.assistant_view import exchange_key, record_key
from ledger_hand.ui.record_panel import CLEAR_KEY, CONFIRM_KEY, KEEP_KEY, RECORD_KEY
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.wiring import Parts
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import row, screened, table
from tests.folder_lock import allow_writing_on_windows, refuse_writing_on_windows
from tests.ui.app_harness import APP_FILE
from tests.ui.assistant_harness import (
    CountingBook,
    captions,
    open_assistant,
    say_on_page,
    to_assistant,
)
from tests.ui.page_harness import to_settings
from tests.ui.screenshot_harness import PNG, Check

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
ONE_BUY = "今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT"
ONE_BUY_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.02 BTC",
    price="94900",
    fee="2 USDT",
    time="今天上午9:40",
    platform="币安",
)
SHARES = "今天15:30在IBKR买了2股MSFT，410美元一股，手续费1美元"
SHARES_ROW = row(
    side="buy",
    coin="MSFT",
    quantity="2股",
    price="410美元",
    fee="1美元",
    time="今天15:30",
    platform="IBKR",
)
READ = "assistant_screenshot_read"
CONTINUE = "assistant_screenshot_continue"
FIRST_UPLOAD = "assistant_screenshot_upload_0"


def answered(text: str) -> ToolReply:
    return ToolReply(text=text, calls=(), record=scripted_record())


def one_buy_model(*more: ToolReply) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD, *more],
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[table(ONE_BUY_ROW)],
    )


def open_with_data(
    model: ModelPort,
    data: Path | None,
    *,
    ledger: FakeLedger | None = None,
    vision_model: ModelPort | None = None,
    steps_refused: str | None = None,
) -> AppTest:
    """The app run once with the demo ledger and the data folder ``data``, on the Assistant page."""
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
        places=DataPlaces(data) if data is not None else None,
        vision_model=vision_model,
        vision_check=Check() if vision_model is not None else None,
        ledger=ledger if ledger is not None else usdt_only_ledger(),
        ledger_kind=LedgerKind.DEMO,
        steps_refused=steps_refused,
    )
    return to_assistant(page.run())


def record_of(data: Path) -> Path:
    return DataPlaces(data).assistant_record


def entries(data: Path) -> list[dict[str, object]]:
    read = read_record(record_of(data))
    assert isinstance(read, RecordRead)
    return [dict(entry) for entry in read.entries]


def panel_texts(page: AppTest) -> list[str]:
    return [str(text.value) for text in page.container(key=RECORD_KEY).text]


def pending(ledger: FakeLedger) -> bool:
    return ledger.proposal_status("proposal-1").status is ProposalStatus.PENDING


def warnings_under(page: AppTest, number: int) -> list[str]:
    return [str(w.value) for w in page.container(key=record_key(number)).warning]


# --- the Assistant page adds to the record ----------------------------------------------


def test_three_things_said_make_three_entries_each_read_back(tmp_path: Path) -> None:
    data = tmp_path / "data"
    model = one_buy_model(answered("Invented answer one."), answered("Invented answer two."))
    page = open_with_data(model, data)

    for words in (ONE_BUY, "我现在持有什么", "那10月呢"):
        page = say_on_page(page, words)

    assert not page.exception
    assert record_of(data).read_bytes().count(b"\n") == 3
    kept = entries(data)
    assert [entry["said"] for entry in kept] == [ONE_BUY, "我现在持有什么", "那10月呢"]
    assert [entry["format_version"] for entry in kept] == [RECORD_VERSION] * 3
    assert kept[0]["sent"] == [
        {"number": 1, "what": "record", "proposal": "proposal-1", "status": "pending"}
    ]
    assert kept[1]["reply"] == "Invented answer one."
    assert kept[0]["at"] == INVENTED_NOW.isoformat()
    for number in (1, 2, 3):
        assert not page.container(key=exchange_key(number)).warning


def test_a_screenshots_entry_holds_none_of_the_pictures_bytes(tmp_path: Path) -> None:
    data = tmp_path / "data"
    model = RoutedModel(
        screen=[screened(("spot_trade", "今天15:30在IBKR买了2股MSFT"))],
        extraction=[table(SHARES_ROW)],
    )
    page = open_with_data(model, data, vision_model=RoutedModel(pictures=[SHARES]))

    page = page.file_uploader(key=FIRST_UPLOAD).set_value(("order.png", PNG, "image/png")).run()
    page = page.button(key=CONTINUE).click().run()

    (entry,) = entries(data)
    assert entry["from_screenshot"] is True
    assert entry["said"] == SHARES
    assert entry["models"] == {
        "tools": ModelSettings().model,
        "vision": ModelSettings().vision_model,
    }
    written = record_of(data).read_bytes()
    assert b"invented picture bytes" not in written
    assert PNG not in written
    assert b"order.png" not in written


@pytest.fixture
def locked(tmp_path: Path) -> Iterator[Path]:
    folder = tmp_path / "locked"
    folder.mkdir()
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    refuse_writing_on_windows(folder)  # Windows ignores the write bit on a folder
    yield folder
    allow_writing_on_windows(folder)
    folder.chmod(stat.S_IRWXU)


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="the superuser writes anywhere"
)
def test_a_folder_that_cannot_be_written_still_sends_and_the_page_says_it_was_not_kept(
    locked: Path,
) -> None:
    ledger = usdt_only_ledger()
    page = open_with_data(one_buy_model(), locked, ledger=ledger)

    page = say_on_page(page, ONE_BUY)

    assert not page.exception
    assert pending(ledger)
    (warning,) = warnings_under(page, 1)
    assert warning.startswith("This was done, but it was not kept in the assistant's record:")
    assert "cannot be written" in warning
    assert list(page.error) == []
    assert list(locked.iterdir()) == []


def test_without_a_data_folder_nothing_is_written_and_the_page_says_no_record(
    tmp_path: Path,
) -> None:
    ledger = usdt_only_ledger()
    page = open_assistant(one_buy_model(), ledger=ledger)

    page = say_on_page(page, ONE_BUY)

    assert pending(ledger)
    assert NO_RECORD in captions(page, exchange_key(1))
    assert list(page.container(key=record_key(1)).warning) == []


# --- a record this program cannot read -----------------------------------------------------


@pytest.mark.parametrize(
    ("held", "reason"),
    [
        (
            json.dumps({"format_version": RECORD_VERSION + 1, "said": "invented"}) + "\n",
            "newer version",
        ),
        (
            json.dumps({"format_version": 1, "said": "a"})
            + "\nnot an entry\n"
            + json.dumps({"format_version": 1, "said": "b"})
            + "\n",
            "cannot be read",
        ),
    ],
    ids=["a newer version", "a line in the middle"],
)
def test_a_record_that_cannot_be_read_is_left_as_it_is_and_both_pages_say_so(
    tmp_path: Path, held: str, reason: str
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    record_of(data).write_text(held, encoding="utf-8")
    before = record_of(data).read_bytes()
    ledger = usdt_only_ledger()

    page = say_on_page(open_with_data(one_buy_model(), data, ledger=ledger), ONE_BUY)

    assert pending(ledger)
    (warning,) = warnings_under(page, 1)
    assert "not kept in the assistant's record" in warning
    assert reason in warning
    page = to_settings(page)
    assert any(t.startswith("Entries: cannot be read:") and reason in t for t in panel_texts(page))
    assert record_of(data).read_bytes() == before


def test_a_last_line_cut_half_way_is_passed_over_and_the_file_is_whole_after(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    whole = json.dumps({"format_version": 1, "said": "invented"}) + "\n"
    record_of(data).write_text(whole + '{"format_version": 1, "sa', encoding="utf-8")

    page = to_settings(open_with_data(one_buy_model(), data))
    assert "Entries: 1 entry. The most recent 1,000 are kept." in panel_texts(page)

    page = say_on_page(to_assistant(page), ONE_BUY)

    assert not page.container(key=exchange_key(1)).warning
    assert [entry["said"] for entry in entries(data)] == ["invented", ONE_BUY]
    assert record_of(data).read_text(encoding="utf-8").startswith(whole)


# --- the Settings page shows and clears it -------------------------------------------------


def test_the_settings_page_says_where_the_record_is_what_it_holds_and_how_many(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    page = open_with_data(one_buy_model(answered("Invented answer.")), data)
    page = say_on_page(say_on_page(page, ONE_BUY), "我现在持有什么")

    page = to_settings(page)

    texts = panel_texts(page)
    assert f"File: {record_of(data)}" in texts
    assert "Entries: 2 entries. The most recent 1,000 are kept." in texts
    words = [str(c.value) for c in page.container(key=RECORD_KEY).caption]
    assert words == [PLAIN_TEXT]
    assert "word for word" in PLAIN_TEXT
    assert "not encrypted" in PLAIN_TEXT
    assert list(page.container(key=RECORD_KEY).error) == []


def test_clearing_takes_two_presses_and_then_there_is_no_file(tmp_path: Path) -> None:
    data = tmp_path / "data"
    page = to_settings(say_on_page(open_with_data(one_buy_model(), data), ONE_BUY))

    page = page.button(key=CLEAR_KEY).click().run()
    assert record_of(data).exists()
    assert any(t.startswith(f"Delete {record_of(data)}?") for t in panel_texts(page))

    page = page.button(key=CONFIRM_KEY).click().run()

    assert not record_of(data).exists()
    texts = panel_texts(page)
    assert "Cleared: the record file was deleted." in texts
    assert "Entries: none yet. The most recent 1,000 are kept." in texts
    assert page.button(key=CLEAR_KEY).disabled


def test_keep_it_asks_no_more_and_deletes_nothing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    page = to_settings(say_on_page(open_with_data(one_buy_model(), data), ONE_BUY))

    page = page.button(key=CLEAR_KEY).click().run()
    page = page.button(key=KEEP_KEY).click().run()

    assert record_of(data).exists()
    assert not page.button(key=CLEAR_KEY).disabled
    assert [b.key for b in page.container(key=RECORD_KEY).button] == [CLEAR_KEY]


def test_a_record_that_cannot_be_read_can_be_cleared_and_the_question_says_it_is_gone(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    newer = json.dumps({"format_version": RECORD_VERSION + 1}) + "\n"
    record_of(data).write_text(newer, encoding="utf-8")

    page = to_settings(open_with_data(RoutedModel(), data))
    page = page.button(key=CLEAR_KEY).click().run()
    question = next(t for t in panel_texts(page) if t.startswith("Delete"))
    assert "This version of the program cannot read this file; once deleted it is gone." in (
        question
    )
    page = page.button(key=CONFIRM_KEY).click().run()

    assert not record_of(data).exists()


def test_without_a_data_folder_the_settings_page_says_there_is_no_record_and_has_no_clear(
    tmp_path: Path,
) -> None:
    page = to_settings(open_with_data(RoutedModel(), None))

    assert any("keeps no record" in t for t in panel_texts(page))
    assert [b.key for b in page.container(key=RECORD_KEY).button] == []


# --- a refused step limit greys the screenshot out too ---------------------------------------


def test_with_a_refused_step_limit_no_screenshot_can_be_given_and_the_vision_model_is_not_asked(
    tmp_path: Path,
) -> None:
    vision = RoutedModel(pictures=["invented text read"])
    page = open_with_data(
        RoutedModel(), tmp_path / "data", vision_model=vision, steps_refused="invented refusal"
    )

    uploads = {str(box.key): bool(box.proto.disabled) for box in page.file_uploader}
    assert uploads == {FIRST_UPLOAD: True}
    with pytest.raises(AppTestError, match="disabled"):
        page.file_uploader(key=FIRST_UPLOAD).set_value(("order.png", PNG, "image/png"))
    page = page.run()

    assert vision.pictures.calls == []
    assert [box.key for box in page.text_area] == []
    assert not (tmp_path / "data").exists()
