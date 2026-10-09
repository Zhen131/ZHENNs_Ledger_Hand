"""Gate: what the first prompt version sends to the model stays exactly what it was.

The first prompt is the baseline every later prompt version is measured
against, so what it sends must not move: the system message, the examples,
the passage, the words for asking again, and the table the reply is held to.
``first_prompt_calls.json`` beside this file was written once, from the code
as it stood before prompt versions could carry a table of their own, and is
never edited. This test makes the same calls again with today's code and
compares the result with that file byte for byte.

Every passage and reply here is invented, and nothing is sent to a real
model: a scripted model records what it is asked.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledger_hand.extraction.extractor import extract
from ledger_hand.extraction.prompting import build_messages
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.reply_parser import ReplyProblem
from ledger_hand.ports import FinishReason, Message, ModelReply, ReplyRecord
from tests.extraction.scripted_runs import NOW, ZONE, row, table
from tests.fakes.scripted_model import ScriptedModel, Step

SAMPLE = Path(__file__).with_name("first_prompt_calls.json")


def _cut_off(text: str) -> ModelReply:
    record = ReplyRecord(
        model="scripted",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.LENGTH_LIMIT,
    )
    return ModelReply(text=text, record=record)


# Each case: a passage, how often to ask again, and the replies the model gives.
_CASES: tuple[tuple[str, int, tuple[Step, ...]], ...] = (
    (
        "今天上午 10 点在 OKX 买了 0.3 ETH，3,150 一个，手续费 0.5U",
        1,
        (
            table(
                row(
                    side="buy",
                    coin="ETH",
                    quantity="0.3 ETH",
                    price="3,150",
                    fee="0.5U",
                    time="今天上午 10 点",
                    platform="OKX",
                )
            ),
        ),
    ),
    (
        "Sold 2,000 ADA at 0.41 yesterday on Kraken",
        1,
        (
            "Here are the trades you asked for.",
            table(
                row(
                    side="sell",
                    coin="ADA",
                    quantity="2,000 ADA",
                    price="0.41",
                    time="yesterday",
                    platform="Kraken",
                )
            ),
        ),
    ),
    (
        "刚 buy 了 50 个 SOL，at 141.2",
        2,
        (
            _cut_off('{"trades": [{"side": "buy", "coin": "SOL", "quan'),
            '{"rows": []}',
            table(row(side="buy", coin="SOL", quantity="50 个 SOL", price="141.2")),
        ),
    ),
)


def _message(message: Message) -> dict[str, str]:
    return {"role": message.role.value, "content": message.content}


def sample() -> str:
    """The calls the first prompt makes today, written as the sample file is."""
    extractions: list[dict[str, object]] = []
    for passage, asks_again, steps in _CASES:
        model = ScriptedModel(steps)
        extract(passage, model, now=NOW, zone=ZONE, asks_again=asks_again)
        extractions.append(
            {
                "passage": passage,
                "asks_again": asks_again,
                "calls": [
                    {
                        "messages": [_message(message) for message in call.messages],
                        "reply_schema": call.reply_schema,
                        "parameters": None if call.parameters is None else repr(call.parameters),
                    }
                    for call in model.calls
                ],
            }
        )
    asking_again = [
        {
            "problem": problem.name,
            "messages": [
                _message(message) for message in build_messages(FIRST_PROMPT, _CASES[0][0], problem)
            ],
        }
        for problem in ReplyProblem
    ]
    data = {
        "prompt": FIRST_PROMPT.name,
        "extractions": extractions,
        "asking_again": asking_again,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def test_the_first_prompt_sends_exactly_what_the_sample_file_holds() -> None:
    assert sample().encode("utf-8") == SAMPLE.read_bytes()


def test_the_sample_holds_asking_again_and_every_problem() -> None:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))

    assert [len(case["calls"]) for case in data["extractions"]] == [1, 2, 3]
    assert [entry["problem"] for entry in data["asking_again"]] == [p.name for p in ReplyProblem]
    for case in data["extractions"]:
        for call in case["calls"]:
            assert call["reply_schema"] is not None
