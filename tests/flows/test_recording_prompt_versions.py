"""Tests of choosing the prompt versions a passage is judged and extracted with.

Left out, they are the versions every caller used before: the model is sent
the same messages, and the progress names the same versions. Chosen, the
model gets the chosen version's words, and the progress names it. The
assistant judges and extracts with the second versions.
Every passage and reply is invented.
"""

from __future__ import annotations

from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first2 import FIRST_PROMPT_2
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.flows.conversation import ASSISTANT_EXTRACT_PROMPT, ASSISTANT_SCREEN_PROMPT
from ledger_hand.flows.progress import Step
from ledger_hand.flows.recording import start
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, row, screened, table

PASSAGE = "昨天晚上8点在币安买了0.1 BTC，价格60000 USDT，手续费0"
ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.1 BTC",
    price="60000 USDT",
    fee="0",
    time="昨天晚上8点",
    platform="币安",
)


def model() -> RoutedModel:
    return RoutedModel(screen=[screened(("spot_trade", "买了0.1 BTC"))], extraction=[table(ROW)])


def test_left_out_the_versions_are_those_used_before_and_the_messages_the_same() -> None:
    left_out, named = model(), model()

    plain = start(PASSAGE, left_out, now=NOW, zone=ZONE)
    chosen = start(
        PASSAGE,
        named,
        now=NOW,
        zone=ZONE,
        screen_prompt=SCREEN_PROMPT,
        extract_prompt=FIRST_PROMPT,
    )

    assert plain.prompts == ((Step.SCREENING, "screen-1"), (Step.EXTRACTION, "first"))
    assert plain.prompts == chosen.prompts
    assert left_out.screen.calls == named.screen.calls
    assert left_out.extraction.calls == named.extraction.calls
    assert plain.records == chosen.records


def test_a_chosen_judging_version_is_the_one_sent_and_named() -> None:
    used = model()

    progress = start(PASSAGE, used, now=NOW, zone=ZONE, screen_prompt=SCREEN_PROMPT_2)

    assert used.screen.calls[0].messages[0].content == SCREEN_PROMPT_2.instructions
    assert progress.prompts[0] == (Step.SCREENING, "screen-2")


def test_the_assistant_judges_and_extracts_with_the_second_versions() -> None:
    assert ASSISTANT_SCREEN_PROMPT is SCREEN_PROMPT_2
    assert ASSISTANT_EXTRACT_PROMPT is FIRST_PROMPT_2
