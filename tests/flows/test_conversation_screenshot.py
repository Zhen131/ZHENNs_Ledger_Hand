"""Tests of recording a screenshot read through the assistant, and who wrote each reply.

The text read off a screenshot, as the person left it, and the note are
recorded exactly as the same words typed: the same asset table, prompt
versions and holding back, the same proposal, the same reasons for a trade
not sent, the same reply. The model that chooses tools is not asked, and
nothing reaches a book. Every sentence, reply and trade is invented.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from ledger_hand.extraction.picture_reading import PictureRead
from ledger_hand.extraction.prompts.read import READ_PROMPT
from ledger_hand.flows.conversation import (
    ASSISTANT_EXTRACT_PROMPT,
    ASSISTANT_SCREEN_PROMPT,
    AssistantChat,
    Route,
    Said,
    ScreenshotText,
    WordsBy,
    say,
    say_from_reading,
)
from ledger_hand.flows.progress import Step as FlowStep
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import Message, Role, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import copied, row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
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
OTHER_UNIT = "今天下午3点在OKX用25U买了ETH，价格3000，手续费0.01 USDT"
OTHER_UNIT_ROW = row(
    side="buy",
    coin="ETH",
    quantity="25U",
    price="3000",
    fee="0.01 USDT",
    time="今天下午3点",
    platform="OKX",
)
NO_FEE = "今天上午9:40在币安买了0.02 BTC，价格94900"
NO_FEE_ROW = row(
    side="buy", coin="BTC", quantity="0.02 BTC", price="94900", time="今天上午9:40", platform="币安"
)


def reading_of(text: str) -> PictureRead:
    return PictureRead(text=text, calls=(scripted_record(),), version=READ_PROMPT.name)


def typed(
    words: str,
    rows: list[dict[str, str]],
    ledger: FakeLedger,
    answers: list[Step] = (),  # type: ignore[assignment]
) -> tuple[Said, RoutedModel]:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(*rows)],
        answers=answers,
    )
    said = say(
        AssistantChat(),
        words,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )
    return said, model


def from_reading(
    words: str, rows: list[dict[str, str]], ledger: FakeLedger, note: str = ""
) -> tuple[Said, RoutedModel]:
    model = RoutedModel(
        screen=[screened(("spot_trade", words.split("，")[0]))], extraction=[table(*rows)]
    )
    said = say_from_reading(
        AssistantChat(),
        ScreenshotText(reading=reading_of(words), text=words, note=note),
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
    )
    return said, model


def what_came(said: Said) -> tuple[object, ...]:
    recorded = said.recorded
    assert recorded is not None
    return (
        said.reply,
        recorded.ending,
        recorded.trades,
        recorded.numbers,
        recorded.left_out,
        said.sent,
    )


@pytest.mark.parametrize(
    ("words", "rows"),
    [(SHARES, [SHARES_ROW]), (OTHER_UNIT, [OTHER_UNIT_ROW])],
    ids=["a share in dollars", "a quantity in another unit"],
)
def test_typed_and_from_a_screenshot_send_and_say_the_same(
    words: str, rows: list[dict[str, str]]
) -> None:
    by_typing, _ = typed(words, rows, FakeLedger())
    by_reading, _ = from_reading(words, rows, FakeLedger())

    assert what_came(by_reading) == what_came(by_typing)


def test_the_screenshot_way_uses_the_assistants_prompts_and_holds_another_unit_back() -> None:
    said, model = from_reading(OTHER_UNIT, [OTHER_UNIT_ROW], FakeLedger())

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NOTHING_TO_SEND
    prompts = dict(said.recorded.progress.prompts)
    assert prompts[FlowStep.READING] == READ_PROMPT.name
    assert ASSISTANT_SCREEN_PROMPT.name in prompts.values()
    assert ASSISTANT_EXTRACT_PROMPT.name in prompts.values()
    assert model.tools.calls == []


def test_a_share_from_a_screenshot_is_sent_priced_in_dollars() -> None:
    ledger = FakeLedger()

    said, model = from_reading(SHARES, [SHARES_ROW], ledger)

    assert said.route is Route.SCREENSHOT
    assert said.sent is not None
    assert said.recorded is not None
    (trade,) = said.recorded.trades
    assert (trade.asset, trade.quote, trade.fee_asset) == ("MSFT", "USD", "USD")
    assert model.tools.calls == []
    assert said.state.chat.items == (
        Message(Role.USER, SHARES),
        Message(Role.ASSISTANT, said.reply),
    )
    assert said.state.chat.proposals == (said.sent.proposals,)
    assert said.words_by is WordsBy.PROGRAM


def test_the_note_is_joined_after_the_text_read() -> None:
    said, _ = from_reading(NO_FEE, [NO_FEE_ROW], usdt_only_ledger(), note="手续费 0.1 USDT")

    assert said.recorded is not None
    assert said.recorded.progress.passage == f"{NO_FEE}\n\n手续费 0.1 USDT"


def test_a_question_from_a_screenshot_waits_and_the_answer_goes_on_as_typed() -> None:
    ledger = usdt_only_ledger()
    model = RoutedModel(
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[table(NO_FEE_ROW)],
        answers=[copied("0.1 USDT")],
    )
    first = say_from_reading(
        AssistantChat(),
        ScreenshotText(reading=reading_of(NO_FEE), text=NO_FEE),
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
    )
    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert first.words_by is WordsBy.QUESTION
    assert first.state.recording is not None

    second = say(
        first.state,
        "手续费 0.1 USDT",
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert second.route is Route.ANSWER
    assert second.sent is not None
    assert model.tools.calls == []


def test_a_screenshot_is_refused_while_something_waits() -> None:
    ledger = usdt_only_ledger()
    first, _ = typed(NO_FEE, [NO_FEE_ROW], ledger)
    assert first.state.recording is not None

    with pytest.raises(ValueError, match="waits"):
        say_from_reading(
            first.state,
            ScreenshotText(reading=reading_of(NO_FEE), text=NO_FEE),
            model=RoutedModel(),
            ledger=ledger,
            now=INVENTED_NOW,
            zone=INVENTED_ZONE,
        )


def test_the_text_as_the_person_left_it_is_what_is_recorded() -> None:
    model = RoutedModel(
        screen=[screened(("spot_trade", "买了2股MSFT"))], extraction=[table(SHARES_ROW)]
    )
    said = say_from_reading(
        AssistantChat(),
        ScreenshotText(reading=reading_of("garbled text read"), text=SHARES),
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
    )

    assert said.recorded is not None
    assert said.recorded.progress.passage == SHARES


def test_a_model_answer_is_by_the_model_and_a_withheld_one_by_the_program() -> None:
    model = RoutedModel(tools=["你好"])
    said = say(
        AssistantChat(),
        "你好",
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )
    assert said.words_by is WordsBy.MODEL

    assert replace(said, turn=None).words_by is WordsBy.PROGRAM
