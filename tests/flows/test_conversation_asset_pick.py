"""Tests of the assistant picking, from the ledger's list, the asset a Chinese name names.

Against the demo book, a scripted model stands in for every call: the
tools, judging, extraction, the pick and the questions. What is checked:
a name picked is sent as the ledger's asset and said in the reply; a name
not picked, for any reason, is asked about as before and nothing ends; a
name the program knows, or that can be a code, is never handed over; one
name said twice is handed over once; a screenshot's text is picked from as
well; and the Record page's way never picks. Every sentence is invented.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

import pytest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.ledger_table import table_of
from ledger_hand.extraction.asset_picking import MOST_LISTED, PickMiss
from ledger_hand.extraction.picture_reading import PictureRead
from ledger_hand.flows import recording
from ledger_hand.flows.conversation import (
    AssistantChat,
    Said,
    ScreenshotText,
    say,
    say_from_reading,
)
from ledger_hand.flows.progress import Step
from ledger_hand.flows.questions import ADD_IN_LEDGER_FIRST
from ledger_hand.flows.record_words import PICKED_WORDS
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.ledger.demo_book import DEMO_ASSETS, demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ModelError, ModelErrorKind, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step as ScriptStep
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import copied, row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)


def said_as(coin: str) -> str:
    return f"2026年11月20号14:30在IBKR买了2股{coin}，100美元一股，手续费1美元"


def row_of(coin: str) -> dict[str, str]:
    return row(
        side="buy",
        coin=coin,
        quantity="2股",
        price="100美元",
        fee="1美元",
        time="2026年11月20号14:30",
        platform="IBKR",
    )


def pick(said: str, code: str) -> str:
    return json.dumps({"said": said, "code": code}, ensure_ascii=False)


def model_for(
    words: str,
    rows: Sequence[dict[str, str]],
    picks: Sequence[ScriptStep] = (),
    answers: Sequence[ScriptStep] = (),
) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(*rows)],
        picks=picks,
        answers=answers,
    )


def talk(model: RoutedModel, *words: str, ledger: FakeLedger | None = None) -> list[Said]:
    ledger = ledger if ledger is not None else demo_ledger()
    state = AssistantChat()
    seen = []
    for one in words:
        said = say(
            state,
            one,
            model=model,
            ledger=ledger,
            now=INVENTED_NOW,
            zone=INVENTED_ZONE,
            max_steps=6,
        )
        seen.append(said)
        state = said.state
    return seen


def picked_line(said: str, code: str, name: str) -> str:
    return PICKED_WORDS.format(said=said, code=code, name=name)


# --- a name picked ---------------------------------------------------------------------


def test_a_chinese_name_picked_is_sent_as_the_ledgers_asset_and_said() -> None:
    words = said_as("微软的股票")
    model = model_for(words, [row_of("微软的股票")], picks=[pick("微软", "MSFT")])
    ledger = demo_ledger()

    (said,) = talk(model, words, ledger=ledger)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    (trade,) = said.recorded.trades
    assert (trade.asset, trade.quantity, trade.price, trade.total) == (
        "MSFT",
        Decimal("2"),
        Decimal("100"),
        Decimal("200"),
    )
    assert (trade.quote, trade.fee, trade.fee_asset) == ("USD", Decimal("1"), "USD")
    line = picked_line("微软", "MSFT", "Microsoft")
    assert line in said.reply.splitlines()
    assert said.reply.count(line) == 1
    progress = said.recorded.progress
    assert [call.step for call in progress.calls].count(Step.ASSET_PICK) == 1
    assert (Step.ASSET_PICK, "asset-pick-1") in progress.prompts
    (found,) = progress.picks
    assert (found.word, found.said, found.code, found.miss) == ("微软的股票", "微软", "MSFT", None)


def test_the_model_is_called_to_pick_at_temperature_zero_with_a_short_reply() -> None:
    words = said_as("微软")
    model = model_for(words, [row_of("微软")], picks=[pick("微软", "MSFT")])

    talk(model, words)

    (call,) = model.picks.calls
    assert call.parameters is not None
    assert call.parameters.temperature == 0
    assert call.parameters.max_reply_tokens == 100
    assert call.messages[-1].content.startswith("Words: 微软\nList:\n")


def test_an_english_name_in_two_words_is_picked() -> None:
    words = said_as("Coca Cola")
    model = model_for(words, [row_of("Coca Cola")], picks=[pick("Coca Cola", "KO")])

    (said,) = talk(model, words)

    assert said.sent is not None
    assert said.recorded is not None and said.recorded.trades[0].asset == "KO"
    assert picked_line("Coca Cola", "KO", "Coca-Cola") in said.reply


def test_a_name_picked_is_said_when_recording_begins_and_when_it_ends_not_between() -> None:
    words = "2026年11月20号14:30在IBKR买了2股微软，100美元一股"
    no_fee = row(
        side="buy",
        coin="微软",
        quantity="2股",
        price="100美元",
        time="2026年11月20号14:30",
        platform="IBKR",
    )
    model = model_for(words, [no_fee], picks=[pick("微软", "MSFT")], answers=[copied("1美元")])

    first, last = talk(model, words, "1美元")

    line = picked_line("微软", "MSFT", "Microsoft")
    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert line in first.reply
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert line in last.reply
    assert len(model.picks.calls) == 1


def test_one_name_said_in_two_trades_is_handed_over_once() -> None:
    words = said_as("微软") + "；又买了3股微软，101美元一股，手续费1美元"
    second = row_of("微软") | {"quantity": "3股", "price": "101美元"}
    model = model_for(words, [row_of("微软"), second], picks=[pick("微软", "MSFT")])

    (said,) = talk(model, words)

    assert len(model.picks.calls) == 1
    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["MSFT", "MSFT"]
    assert said.reply.count(picked_line("微软", "MSFT", "Microsoft")) == 1


# --- a name not picked -----------------------------------------------------------------


def assert_asked_about_the_asset(said: Said) -> None:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert said.recorded.progress.trades[0].status.name == "OPEN"
    assert said.reply.startswith("[Trade 1 of 1: asset]")
    assert ADD_IN_LEDGER_FIRST in said.reply
    assert "coin" not in said.reply.casefold()
    assert "币" not in said.reply
    assert said.sent is None
    assert "Took " not in said.reply


def test_a_name_the_list_lacks_sends_nothing_and_asks_which_asset() -> None:
    words = said_as("特斯拉")
    model = model_for(words, [row_of("特斯拉")], picks=[pick("特斯拉", "")])

    (said,) = talk(model, words)

    assert_asked_about_the_asset(said)
    assert said.recorded is not None
    (found,) = said.recorded.progress.picks
    assert found.miss is PickMiss.NONE_ON_LIST


@pytest.mark.parametrize(
    ("coin", "step", "miss"),
    [
        ("微软", pick("微软", "TSLA"), PickMiss.CODE_NOT_ON_LIST),
        ("微软", pick("微软", "USD"), PickMiss.CODE_NOT_ON_LIST),
        ("微软", pick("苹果", "AAPL"), PickMiss.SAID_NOT_IN_WORDS),
        ("以太坊经典", pick("以太坊", "ETH"), PickMiss.WORDS_LEFT_OVER),
        ("微软", '{"code": "MSFT"}', PickMiss.REPLY_UNREADABLE),
        ("微软", ModelError(ModelErrorKind.TIMED_OUT, "slow"), PickMiss.MODEL_FAILED),
    ],
)
def test_a_pick_not_taken_asks_which_asset_and_ends_nothing(
    coin: str, step: ScriptStep, miss: PickMiss
) -> None:
    words = said_as(coin)
    model = model_for(words, [row_of(coin)], picks=[step])

    (said,) = talk(model, words)

    assert_asked_about_the_asset(said)
    assert said.recorded is not None
    (found,) = said.recorded.progress.picks
    assert found.miss is miss


def test_after_a_miss_the_code_answered_is_recorded() -> None:
    words = said_as("微软")
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(row_of("微软"))],
        picks=[pick("微软", "")],
        answers=[copied("MSFT")],
    )

    first, last = talk(model, words, "MSFT")

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert last.recorded.trades[0].asset == "MSFT"
    assert "Took " not in last.reply


# --- names never handed over -----------------------------------------------------------


@pytest.mark.parametrize(
    ("coin", "ending"),
    [
        ("TSLA", RecordEnding.NOTHING_TO_SEND),
        ("狗狗币", RecordEnding.NOTHING_TO_SEND),
        ("USDT", RecordEnding.NOTHING_TO_SEND),
        ("Microsoft", RecordEnding.SENT),
    ],
)
def test_a_code_a_shielded_coin_money_or_the_ledgers_own_name_is_not_handed_over(
    coin: str, ending: RecordEnding
) -> None:
    words = said_as(coin)
    model = model_for(words, [row_of(coin)])

    (said,) = talk(model, words)

    assert model.picks.calls == []
    assert said.recorded is not None and said.recorded.ending is ending
    assert said.recorded.progress.picks == ()
    if coin in ("TSLA", "狗狗币"):
        (left,) = said.recorded.left_out
        assert left.why is LeftOut.NOT_IN_LEDGER
    if coin == "Microsoft":
        assert said.recorded.trades[0].asset == "MSFT"


def test_a_ledger_of_more_than_five_hundred_assets_traded_is_not_handed_over() -> None:
    assets = [
        Asset(
            id="usd", code="USD", name="US dollar", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
        )
    ]
    assets += [
        Asset(
            id=f"a{number}",
            code=f"A{number}",
            name=f"Company {number}",
            kind=AssetKind.STOCK,
            pricing=Pricing.CANNOT_PRICE,
        )
        for number in range(MOST_LISTED + 1)
    ]
    words = said_as("微软")
    model = model_for(words, [row_of("微软")])

    (said,) = talk(model, words, ledger=FakeLedger(assets=assets, trades=()))

    assert model.picks.calls == []
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    (found,) = said.recorded.progress.picks
    assert found.miss is PickMiss.LIST_TOO_LONG


# --- a screenshot, and the Record page ---------------------------------------------------


def test_a_screenshots_text_is_picked_from_as_well() -> None:
    text = said_as("微软")
    model = RoutedModel(
        screen=[screened(("spot_trade", text.split("，")[0]))],
        extraction=[table(row_of("微软"))],
        picks=[pick("微软", "MSFT")],
    )
    shot = ScreenshotText(reading=PictureRead(text=text, version="read-1", calls=()), text=text)

    said = say_from_reading(
        AssistantChat(),
        shot,
        model=model,
        ledger=demo_ledger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
    )

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    assert said.recorded.trades[0].asset == "MSFT"
    assert picked_line("微软", "MSFT", "Microsoft") in said.reply


def test_the_record_pages_way_never_hands_a_name_over() -> None:
    words = said_as("微软")
    model = model_for(words, [row_of("微软")], picks=[pick("微软", "MSFT")])

    progress = recording.start(
        words, model, now=INVENTED_NOW, zone=INVENTED_ZONE, assets=BUILT_IN_ASSETS
    )

    assert model.picks.calls == []
    assert progress.picks == ()
    assert all(call.step is not Step.ASSET_PICK for call in progress.calls)


def test_with_picking_left_off_the_ledgers_table_never_hands_a_name_over() -> None:
    words = said_as("微软")
    model = model_for(words, [row_of("微软")], picks=[pick("微软", "MSFT")])
    table_made = table_of(DEMO_ASSETS)
    assert table_made is not None

    progress = recording.start(
        words, model, now=INVENTED_NOW, zone=INVENTED_ZONE, assets=table_made
    )

    assert model.picks.calls == []
    assert progress.picks == ()
