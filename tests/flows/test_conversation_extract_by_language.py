"""Tests of the extraction version the assistant reads a passage with, by its language.

Words with a Chinese character in them, once tidied, are extracted with the
version for Chinese: the assistant's own, or the one handed to ``say``.
Words with none are extracted with ``first-3``, whatever is handed in. A
screenshot is extracted with ``first-3``. The rule lives in one function,
and tidying asks the same pattern for a Chinese character. Every sentence
and trade is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.core import spoken_text
from ledger_hand.core.chinese import CHINESE_CHARACTER, holds_chinese
from ledger_hand.extraction.prompt_language import ENGLISH_EXTRACT_PROMPT, extract_prompt_for
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.spoken1 import SPOKEN_PROMPT_1
from ledger_hand.flows.conversation import (
    ASSISTANT_CHINESE_EXTRACT_PROMPT,
    ASSISTANT_EXTRACT_PROMPT,
    AssistantChat,
    ScreenshotText,
    say,
    say_from_reading,
)
from ledger_hand.flows.progress import Step
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_conversation_screenshot import RECORD, reading_of

CHINESE = "今天15:30在IBKR买了2股MSFT，410美元一股，手续费1美元"
CHINESE_ROW = row(
    side="buy",
    coin="MSFT",
    quantity="2股",
    price="410美元",
    fee="1美元",
    time="今天15:30",
    platform="IBKR",
)
ENGLISH = "Bought 2 MSFT shares on IBKR today at 15:30, 410 USD each, commission 1 USD"
ENGLISH_ROW = row(
    side="buy",
    coin="MSFT",
    quantity="2 MSFT shares",
    price="410 USD",
    fee="1 USD",
    time="today at 15:30",
    platform="IBKR",
)


def _model(words: str, found: dict[str, str]) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD], screen=[screened(("spot_trade", words[:10]))], extraction=[table(found)]
    )


def _extracted_with(words: str, found: dict[str, str], **handed: object) -> str:
    model = _model(words, found)
    said = say(
        AssistantChat(),
        words,
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        **handed,  # type: ignore[arg-type]
    )
    assert said.recorded is not None
    assert model.extraction.calls[0].messages[0].content in {
        SPOKEN_PROMPT_1.instructions,
        FIRST_PROMPT_3.instructions,
    }
    return dict(said.recorded.progress.prompts)[Step.EXTRACTION]


def test_words_with_chinese_go_to_the_version_for_chinese_and_others_to_first_3() -> None:
    assert extract_prompt_for("今天买了 2 ETH", SPOKEN_PROMPT_1) is SPOKEN_PROMPT_1
    assert extract_prompt_for("Bought 2 ETH today", SPOKEN_PROMPT_1) is FIRST_PROMPT_3
    assert extract_prompt_for("今天买了 2 ETH", FIRST_PROMPT_3) is FIRST_PROMPT_3
    assert ENGLISH_EXTRACT_PROMPT is FIRST_PROMPT_3


@pytest.mark.parametrize("text", ["〇", "买", "Bought 2 ETH，今天"])
def test_one_chinese_character_is_enough(text: str) -> None:
    assert holds_chinese(text)


@pytest.mark.parametrize("text", ["", "Bought 2 ETH at 3,400 USDT", "0.5 BTC，¥", "２ ＥＴＨ"])
def test_no_chinese_character_is_no_chinese(text: str) -> None:
    assert not holds_chinese(text)


def test_tidying_asks_the_same_pattern_for_a_chinese_character() -> None:
    assert spoken_text._CHINESE is CHINESE_CHARACTER


def test_a_version_handed_for_chinese_reads_chinese_and_only_chinese() -> None:
    handed = {"extract_for_chinese": SPOKEN_PROMPT_1}

    assert _extracted_with(CHINESE, CHINESE_ROW, **handed) == "spoken-1"
    assert _extracted_with(ENGLISH, ENGLISH_ROW, **handed) == "first-3"


def test_with_nothing_handed_chinese_is_read_with_the_assistant_s_own_version() -> None:
    assert _extracted_with(CHINESE, CHINESE_ROW) == ASSISTANT_CHINESE_EXTRACT_PROMPT.name
    assert _extracted_with(ENGLISH, ENGLISH_ROW) == "first-3"


def test_the_version_sent_to_the_model_is_the_one_named() -> None:
    model = _model(CHINESE, CHINESE_ROW)

    say(
        AssistantChat(),
        CHINESE,
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        extract_for_chinese=SPOKEN_PROMPT_1,
    )

    assert model.extraction.calls[0].messages[0].content == SPOKEN_PROMPT_1.instructions


def test_a_screenshot_in_chinese_is_read_with_first_3() -> None:
    model = RoutedModel(
        screen=[screened(("spot_trade", CHINESE[:10]))], extraction=[table(CHINESE_ROW)]
    )

    said = say_from_reading(
        AssistantChat(),
        ScreenshotText(reading=reading_of(CHINESE), text=CHINESE),
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
    )

    assert said.recorded is not None
    assert dict(said.recorded.progress.prompts)[Step.EXTRACTION] == ASSISTANT_EXTRACT_PROMPT.name
    assert ASSISTANT_EXTRACT_PROMPT is FIRST_PROMPT_3
