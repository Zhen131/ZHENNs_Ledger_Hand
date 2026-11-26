"""Tests of the card the Assistant page draws for each trade sent, and the setting behind it.

The page runs headless with the demo ledger (the demo book, "now" its
fixed moment) and a scripted model. The card of the fourth sentence of the
product owner's examples shows the price in red with "SUSPICIOUS:" and the
reason, and the total as worked out by the program; nothing on a card can
change the trade; a reason is shown as written, whatever characters it
holds. A refused price-gap setting stops the Assistant page alone. Every
sentence and figure is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.marks import Field, FieldMark, MarkKind, TradeMarks
from ledger_hand.core.price_check import PriceCheck, PriceVerdict
from ledger_hand.core.trade import Side
from ledger_hand.flows import recording
from ledger_hand.flows.progress import Progress
from ledger_hand.flows.recorded import MarkedTrade, Recorded, RecordEnding
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_TRADES, demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from ledger_hand.settings import PRICE_GAP_TIMES_VARIABLE
from ledger_hand.ui.assistant_cards import save_key
from ledger_hand.ui.assistant_trade_cards import (
    NOT_CHECKED,
    SUSPICIOUS_TAG,
    TAGS,
    card_key,
    cell_key,
)
from ledger_hand.ui.assistant_view import exchange_key
from ledger_hand.ui.session import BUILDER_KEY
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import APP_FILE
from tests.ui.assistant_harness import open_assistant, say_on_page, texts_of, to_assistant
from tests.ui.test_page_assistant_settings import ScriptedBuilds

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
FOURTH = "今天上午11点在币安0.01个BTC 花了950U，手续费0"
FOURTH_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.01个BTC",
    price="950U",
    fee="0",
    time="今天上午11点",
    platform="币安",
)


def said_on_page(words: str, cells: dict[str, str], ledger: FakeLedger) -> AppTest:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", cells["coin"]))],
        extraction=[table(cells)],
    )
    return say_on_page(open_assistant(model, ledger=ledger), words)


def markdown_of(page: AppTest, key: str) -> list[str]:
    return [str(one.value) for one in page.container(key=key).markdown]


def test_the_fourth_sentence_shows_the_price_suspicious_and_the_total_worked_out() -> None:
    page = said_on_page(FOURTH, FOURTH_ROW, demo_ledger())

    price = cell_key(1, 1, "Price")
    assert texts_of(page, price)[0] == "Price: 950 USDT"
    assert markdown_of(page, price) == [SUSPICIOUS_TAG]
    assert ":red[" in SUSPICIOUS_TAG and "SUSPICIOUS:" in SUSPICIOUS_TAG
    reason = texts_of(page, price)[1]
    assert reason.startswith("far from the market price of BTC in the ledger, 64880 USDT")
    total = cell_key(1, 1, "Total")
    assert texts_of(page, total) == ["Total: 9.5 USDT", "worked out as quantity × price"]
    assert markdown_of(page, total) == [TAGS[MarkKind.COMPUTED]]
    assert markdown_of(page, cell_key(1, 1, "Quantity")) == []


def test_a_card_holds_no_input_and_no_button() -> None:
    page = said_on_page(FOURTH, FOURTH_ROW, demo_ledger())

    card = page.container(key=card_key(1, 1))
    for kind in ("text_input", "number_input", "selectbox", "text_area", "button", "checkbox"):
        assert len(getattr(card, kind)) == 0, kind
    assert page.button(key=save_key("proposal-1")) is not None


def test_the_reply_container_reads_as_before_with_the_card_beside_it() -> None:
    page = said_on_page(FOURTH, FOURTH_ROW, demo_ledger())

    reply = texts_of(page, exchange_key(1))[0]
    assert reply.startswith("Sent to the ledger.")
    assert "far from the market price" in reply
    assert all("SUSPICIOUS" not in line for line in texts_of(page, exchange_key(1)))


def test_a_price_not_compared_says_so_under_the_card() -> None:
    ledger = FakeLedger(
        assets=DEMO_ASSETS, trades=DEMO_TRADES, prices={("ETH", "USD"): Decimal("2700")}
    )
    cells = row(
        side="buy",
        coin="ETH",
        quantity="0.1个ETH",
        price="2600 USDT",
        fee="0",
        time="今天上午10点",
    )
    page = said_on_page("今天上午10点买了0.1个ETH，成交价2600 USDT，手续费0", cells, ledger)

    lines = texts_of(page, card_key(1, 1))
    assert lines[-1].startswith(NOT_CHECKED)
    assert "USD" in lines[-1] and "USDT" in lines[-1]
    assert markdown_of(page, cell_key(1, 1, "Price")) == []


def test_a_day_alone_shows_none_for_the_time_of_day_and_no_mark() -> None:
    cells = row(
        side="buy",
        coin="ETH",
        quantity="0.1个ETH",
        price="2600 USDT",
        fee="0",
        time="11月20号",
    )
    page = said_on_page("11月20号买了0.1个ETH，价格2600 USDT，手续费0", cells, demo_ledger())

    when = cell_key(1, 1, "Time of day")
    assert texts_of(page, when) == ["Time of day: none"]
    assert markdown_of(page, when) == []
    assert texts_of(page, cell_key(1, 1, "Day")) == ["Day: 2026-11-20"]


# --- a reason is shown as written ----------------------------------------------------------

ODD_REASON = "far from *it* _so_ <b>bold</b> :red[x] `code`"


def _one_card(reason: str) -> None:
    """The page script: one card, drawn from a proposal made here (run on its own)."""
    from ledger_hand.ui import assistant_trade_cards
    from tests.ui.test_page_assistant_marks import with_reason

    assistant_trade_cards.draw(with_reason(reason), 1)


def with_reason(reason: str) -> Recorded:
    """A proposal of one trade sent, its price marked suspicious for ``reason``."""
    marks = TradeMarks(marks=(FieldMark(Field.PRICE, MarkKind.SUSPICIOUS, reason),))
    return Recorded(
        ending=RecordEnding.SENT,
        progress=a_progress(),
        trades=(a_trade(),),
        numbers=(1,),
        marked=(MarkedTrade(marks=marks, price=PriceCheck(verdict=PriceVerdict.WITHIN)),),
    )


def a_trade() -> TradeFacts:
    return TradeFacts(
        occurred=datetime(2026, 11, 24, 10, 0, tzinfo=ZoneInfo("Europe/Budapest")),
        side=Side.BUY,
        asset="BTC",
        quantity=Decimal("0.01"),
        price=Decimal("950"),
        total=Decimal("9.5"),
        quote="USDT",
        fee=Decimal("0"),
        fee_asset="USDT",
        platform="",
        note="",
        raw_text="invented",
        zone="Europe/Budapest",
        date_only=False,
        cost_rate=None,
    )


def a_progress() -> Progress:
    return recording.unbegun("invented", now=INVENTED_NOW, zone=INVENTED_ZONE)


def test_a_reason_is_shown_as_plain_text_whatever_it_holds() -> None:
    page = AppTest.from_function(_one_card, args=(ODD_REASON,), default_timeout=30).run()

    price = cell_key(1, 1, "Price")
    assert texts_of(page, price) == ["Price: 950 USDT", ODD_REASON]
    assert markdown_of(page, price) == [SUSPICIOUS_TAG]
    assert not page.exception


# --- the setting --------------------------------------------------------------------------


def test_a_refused_price_gap_stops_the_assistant_page_alone(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PRICE_GAP_TIMES_VARIABLE, "1")
    model = RoutedModel()
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[BUILDER_KEY] = ScriptedBuilds(model)
    page = page.run()

    assert list(page.error) == []
    assert [box.key for box in page.chat_input] == ["chat_input"]

    page = to_assistant(page)
    notice = str(page.container(key="assistant_notice").warning[0].value)
    assert notice.startswith("The assistant cannot start:")
    assert PRICE_GAP_TIMES_VARIABLE in notice
    assert page.chat_input(key="assistant_chat_input").proto.disabled
    assert model.tools.calls == []
