"""Tests of words tidied on the assistant's way: the model sees them, the ledger the words said.

Each thing typed or answered is tidied before anything else. The model that
chooses tools, the judging and the extraction steps all see the words
tidied, so a scripted model here copies its phrases from them; each trade
sent carries the words as the user said them. A screenshot's text is not
tidied, and the record page never is. Every sentence, figure and reply is
invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.followup import AskCell, Cell
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.flows import recording
from ledger_hand.flows.assistant_record import entry_for
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.proposing import propose
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import Message, Role
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step
from tests.flows.scripted_flow import copied, row, screened, table
from tests.flows.test_conversation_screenshot import RECORD, SHARES, SHARES_ROW, from_reading

SAID = (
    "二六年十一月二十号下午十四点十二分在币安买了零点零零五个BTC，"
    "均价六万四千五百三十点二USDT，手续费零点二五USDT"
)
TIDIED = "2026年11月20号下午14点12分在币安买了0.005个BTC，均价64530.2USDT，手续费0.25USDT"
ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.005个BTC",
    price="64530.2USDT",
    fee="0.25USDT",
    time="2026年11月20号下午14点12分",
    platform="币安",
)
NO_FEE = "二六年十一月二十号下午十四点十二分在币安买了零点零零五个BTC，均价六万四千五百三十点二USDT"
NO_FEE_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.005个BTC",
    price="64530.2USDT",
    time="2026年11月20号下午14点12分",
    platform="币安",
)


def _model(rows: list[dict[str, str]], answers: list[Step] = ()) -> RoutedModel:  # type: ignore[assignment]
    return RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "2026年11月20号下午14点12分"))],
        extraction=[table(*rows)],
        answers=answers,
    )


def _say(
    words: str, model: RoutedModel, ledger: FakeLedger, state: AssistantChat | None = None
) -> Said:
    return say(
        state or AssistantChat(),
        words,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


def _user_words(model: RoutedModel) -> list[str]:
    """What the model that chooses tools was told the user said, each time it was asked."""
    return [
        item.content
        for call in model.tools.calls
        for item in call.items
        if isinstance(item, Message) and item.role is Role.USER
    ]


def test_a_trade_said_in_number_words_is_sent_with_its_figures_and_the_words_as_said() -> None:
    ledger = FakeLedger()
    model = _model([ROW])

    said = _say(SAID, model, ledger)

    assert said.read_as is not None
    assert said.read_as.text == TIDIED
    assert _user_words(model) == [TIDIED]
    assert TIDIED in model.extraction.calls[0].messages[-1].content
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    (trade,) = said.recorded.trades
    assert trade.occurred == datetime(2026, 11, 20, 14, 12, tzinfo=ZoneInfo(INVENTED_ZONE))
    assert (trade.quantity, trade.price, trade.total, trade.fee) == (
        Decimal("0.005"),
        Decimal("64530.2"),
        Decimal("322.651"),
        Decimal("0.25"),
    )
    assert trade.raw_text == SAID
    assert said.sent is not None
    assert ledger.proposal_status(said.sent.proposal).status is ProposalStatus.PENDING
    assert ledger.said == [SAID]


def test_an_answer_in_number_words_is_tidied_and_the_first_words_still_go_to_the_ledger() -> None:
    ledger = FakeLedger()
    model = _model([NO_FEE_ROW], answers=[copied("0.03个USDT")])

    asked = _say(NO_FEE, model, ledger)
    assert asked.recorded is not None and asked.recorded.question is not None
    assert asked.recorded.question.asked == AskCell(Cell.FEE, asked.recorded.question.asked.because)
    answered = _say("手续费零点零三个USDT", model, ledger, asked.state)

    assert answered.read_as is not None
    assert answered.read_as.text == "手续费0.03个USDT"
    assert answered.recorded is not None and answered.recorded.ending is RecordEnding.SENT
    (trade,) = answered.recorded.trades
    assert trade.fee == Decimal("0.03")
    assert trade.raw_text == NO_FEE
    assert answered.state.chat.items[-2] == Message(Role.USER, "手续费0.03个USDT")


def test_a_time_said_with_another_zone_reaches_the_model_as_it_was_said() -> None:
    words = "北京时间二六年十一月二十号下午三点在币安买了零点零零五个BTC"
    model = _model([])

    said = _say(words, model, FakeLedger())

    assert said.read_as is not None
    assert said.read_as.text == "北京时间二六年十一月二十号下午三点在币安买了0.005个BTC"
    assert _user_words(model) == [said.read_as.text]


def test_words_in_english_reach_the_model_exactly_as_typed() -> None:
    words = "Bought 0.02 BTC at 94900 at 9:40:15 on 20 November 2026, fee 2 USDT"
    model = _model([])

    said = _say(words, model, FakeLedger())

    assert said.read_as is not None
    assert not said.read_as.changed
    assert _user_words(model) == [words]


def test_a_screenshot_s_text_is_not_tidied() -> None:
    said, _ = from_reading(SHARES, [SHARES_ROW], FakeLedger())

    assert said.read_as is None
    assert said.recorded is not None
    assert said.recorded.progress.raw_text is None


def test_the_record_page_s_way_sends_the_passage_as_the_words_said() -> None:
    model = RoutedModel(screen=[screened(("spot_trade", "x"))], extraction=[table(ROW)])
    progress = recording.start(TIDIED, model, now=INVENTED_NOW, zone=INVENTED_ZONE)
    ledger = FakeLedger()

    recorded = propose(progress, ledger)

    assert progress.raw_text is None
    assert [trade.raw_text for trade in recorded.trades] == [TIDIED]


def test_the_record_keeps_the_words_tidied_beside_the_words_said() -> None:
    said = _say(SAID, _model([ROW]), FakeLedger())

    entry = entry_for(said, words=SAID, at=INVENTED_NOW, model="invented-model")

    assert entry["said"] == SAID
    assert entry["read_as"]["text"] == TIDIED
    assert entry["read_as"]["changes"][0] == {"kind": "year", "said": "二六", "written": "2026"}


def test_the_record_has_no_words_tidied_when_nothing_was_changed() -> None:
    words = "Bought 0.02 BTC at 94900"
    said = _say(words, _model([]), FakeLedger())

    assert entry_for(said, words=words, at=INVENTED_NOW, model="invented-model")["read_as"] is None
