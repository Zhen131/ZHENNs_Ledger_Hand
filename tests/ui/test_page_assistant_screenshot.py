"""Tests of the Assistant page's screenshot, of each page keeping its own, and of the cloud plug.

A screenshot uploaded on the Assistant page is read by the scripted vision
model, its text checked and changed in the box, and Continue records it the
way typed words are recorded: the model that chooses tools is not asked and
the book is never touched. A screenshot read on one page is not seen on the
other. With the cloud plug the page says the assistant does not run on it,
greys the input out and shows no error box. Every picture is a few invented
bytes made in memory; every reply is invented.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ModelError, ModelErrorKind, ToolCall, ToolReply
from ledger_hand.settings import ModelSettings, Plug, Secret
from ledger_hand.ui.assistant_view import exchange_key, table_key
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table
from tests.ui.assistant_harness import (
    INPUT_KEY,
    CountingBook,
    captions,
    errors,
    open_assistant,
    rows_of,
    say_on_page,
    to_assistant,
)
from tests.ui.page_harness import to_record
from tests.ui.screenshot_harness import PNG, Check

READ = "assistant_screenshot_read"
NOTE = "assistant_screenshot_note"
CONTINUE = "assistant_screenshot_continue"
RECORD_READ = "screenshot_read"
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
NO_FEE = "今天15:30在IBKR买了2股MSFT，410美元一股"
NO_FEE_ROW = row(
    side="buy", coin="MSFT", quantity="2股", price="410美元", time="今天15:30", platform="IBKR"
)


def upload_keys(page: AppTest) -> dict[str, bool]:
    """Every upload box on the page: its key and whether it is greyed out."""
    return {str(box.key): bool(box.proto.disabled) for box in page.file_uploader}


def upload_on(page: AppTest, key: str) -> AppTest:
    return page.file_uploader(key=key).set_value(("order.png", PNG, "image/png")).run()


def opened(model: RoutedModel, vision: RoutedModel, book: CountingBook | None = None) -> AppTest:
    return open_assistant(model, ledger=FakeLedger(), book=book, vision_model=vision, check=Check())


def test_a_screenshot_read_changed_and_continued_is_recorded_without_tools_or_book() -> None:
    book = CountingBook()
    model = RoutedModel(
        screen=[screened(("spot_trade", "今天15:30在IBKR买了2股MSFT"))],
        extraction=[table(SHARES_ROW)],
    )
    page = opened(model, RoutedModel(pictures=["MSFT 2 410 USD"]), book)

    page = upload_on(page, "assistant_screenshot_upload_0")
    assert page.text_area(key=READ).value == "MSFT 2 410 USD"
    assert upload_keys(page) == {"assistant_screenshot_upload_1": True}

    page.text_area(key=READ).input(SHARES)
    page = page.button(key=CONTINUE).click().run()

    (trade,) = rows_of(page, table_key(2, "proposed"))
    assert (trade["Asset"], trade["Price"]) == ("MSFT", "410 USD")
    assert model.tools.calls == []
    assert book.calls == []
    assert [str(m.text[0].value) for m in page.chat_message if m.name == "user"] == [SHARES]
    assert [b.key for b in page.text_area] == []


def test_a_screenshot_with_the_fee_missing_asks_and_the_upload_box_is_grey_meanwhile() -> None:
    model = RoutedModel(
        screen=[screened(("spot_trade", "今天15:30在IBKR买了2股MSFT"))],
        extraction=[table(NO_FEE_ROW)],
    )
    page = opened(model, RoutedModel(pictures=[NO_FEE]))

    page = upload_on(page, "assistant_screenshot_upload_0")
    page = page.button(key=CONTINUE).click().run()

    assert "Sent to the ledger: nothing" in captions(page, exchange_key(2))
    assert all(upload_keys(page).values())
    assert model.tools.calls == []


def test_a_screenshot_read_on_the_record_page_is_not_seen_on_the_assistant_page() -> None:
    page = opened(RoutedModel(), RoutedModel(pictures=["read on the record page"]))
    page = to_record(page)

    page = upload_on(page, "screenshot_upload_0")
    assert page.text_area(key=RECORD_READ).value == "read on the record page"

    page = to_assistant(page)
    assert [b.key for b in page.text_area] == []
    assert upload_keys(page) == {"assistant_screenshot_upload_0": False}


def test_a_screenshot_read_on_the_assistant_page_is_not_seen_on_the_record_page() -> None:
    page = opened(RoutedModel(), RoutedModel(pictures=["read on the assistant page"]))

    page = upload_on(page, "assistant_screenshot_upload_0")
    assert page.text_area(key=READ).value == "read on the assistant page"

    page = to_record(page)
    assert [b.key for b in page.text_area] == []
    assert upload_keys(page) == {"screenshot_upload_0": False}
    assert page.session_state["ledger_hand.assistant.screenshot.reading"] is not None


def test_with_the_cloud_plug_one_fixed_sentence_a_grey_input_and_no_error_box() -> None:
    settings = ModelSettings(
        plug=Plug.CLOUD,
        base_url="https://api.example.com/v1",
        model="invented-cloud-model",
        api_key=Secret("sk-invented-assistant-cloud-0123456789"),
    )
    model = RoutedModel()

    page = open_assistant(model, ledger=FakeLedger(), settings=settings)

    notice = str(page.container(key="assistant_notice").warning[0].value)
    assert notice.startswith("Cloud models are not supported for the assistant yet")
    assert page.chat_input(key=INPUT_KEY).proto.disabled
    assert list(page.error) == []
    assert list(page.exception) == []
    assert model.tools.calls == []


def test_with_the_cloud_plug_a_screenshot_is_turned_down_as_on_the_record_page() -> None:
    settings = ModelSettings(
        plug=Plug.CLOUD,
        base_url="https://api.example.com/v1",
        model="invented-cloud-model",
        api_key=Secret("sk-invented-assistant-cloud-0123456789"),
    )
    page = open_assistant(RoutedModel(), ledger=FakeLedger(), settings=settings)

    page = upload_on(page, "assistant_screenshot_upload_0")

    (said,) = errors(page, exchange_key(1))
    assert said.startswith("A screenshot is read through the local plug only")
    assert list(page.exception) == []


def test_the_vision_list_not_clear_says_the_servers_side_not_the_passage() -> None:
    unclear = ModelError(ModelErrorKind.MALFORMED_REPLY, "invented: the list could not be read")
    page = open_assistant(
        RoutedModel(),
        ledger=FakeLedger(),
        vision_model=RoutedModel(),
        check=Check(unclear),
    )

    page = upload_on(page, "assistant_screenshot_upload_0")

    (said,) = errors(page, exchange_key(1))
    assert "did not answer clearly whether it has the vision model" in said
    assert "another way" not in said


def test_typing_while_a_screenshot_waits_says_to_continue_or_drop_first() -> None:
    page = opened(RoutedModel(), RoutedModel(pictures=["MSFT 2 410 USD"]))
    page = upload_on(page, "assistant_screenshot_upload_0")

    page = say_on_page(page, "我现在持有什么")

    texts = [str(t.value) for t in page.container(key=exchange_key(2)).text]
    assert texts[0].startswith("A screenshot waits to be checked")


def test_a_tool_call_model_is_never_handed_a_picture() -> None:
    record = ToolReply(
        text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
    )
    model = RoutedModel(tools=[record])

    page = opened(model, RoutedModel(pictures=["MSFT 2 410 USD"]))
    page = upload_on(page, "assistant_screenshot_upload_0")

    assert model.pictures.calls == []
    assert model.tools.calls == []
