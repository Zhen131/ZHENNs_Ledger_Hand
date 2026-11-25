"""Tests of ``scripts/try_assistant.py`` printing what came of picking an asset from the list.

The script starts with the demo book when no ledger is handed in. A name
picked prints the code taken and the words the model picked out; a name
missed prints why; an answer that follows prints no such line again. A
scripted model stands in for every call; every sentence is invented.
"""

from __future__ import annotations

import io
import json

from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step
from tests.flows.scripted_flow import copied, screened, table
from tests.flows.test_conversation_asset_pick import RECORD, row_of, said_as


def run(words: list[str], coin: str, picks: list[Step], answers: list[Step] = ()) -> str:  # type: ignore[assignment]
    row = row_of(coin) if not answers else row_of(coin) | {"fee": ""}
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words[0].split("，")[0]))],
        extraction=[table(row)],
        picks=picks,
        answers=answers,
    )
    out = io.StringIO()
    try_assistant.main(words, out=out, model=model, max_steps=6)
    return out.getvalue()


def pick(said: str, code: str) -> str:
    return json.dumps({"said": said, "code": code}, ensure_ascii=False)


def test_a_name_picked_prints_the_code_and_the_words_picked_out() -> None:
    printed = run([said_as("微软的股票")], "微软的股票", [pick("微软", "MSFT")])

    assert '  asset picked: "微软的股票" -> MSFT (the model picked out "微软")' in printed
    assert "buy 2 MSFT at 100 USD, total 200 USD, fee 1 USD" in printed


def test_a_name_missed_prints_why() -> None:
    printed = run([said_as("特斯拉")], "特斯拉", [pick("特斯拉", "")])

    assert '  asset not picked: "特斯拉" (the model said the list does not hold it)' in printed


def test_an_answer_that_follows_prints_no_pick_again() -> None:
    words = said_as("微软").replace("，手续费1美元", "")
    printed = run([words, "1美元"], "微软", [pick("微软", "MSFT")], answers=[copied("1美元")])

    assert printed.count("asset picked:") == 1
