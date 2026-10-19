"""An empty reply from the local plug is said in the words the model comparison counts it by.

The model comparison (``evals.compare_models``) counts a sentence's failure
as an empty reply when its message holds ``_EMPTY_REPLY``. This ties the
two together: an answer whose text is blank, with or without some thinking
beside it, fails as ``MALFORMED_REPLY`` with those words in its message, for
a call with pictures as for any other. Should the plug's words change, this
fails, rather than empty replies going uncounted.

It also keeps what a thinking model's record says when the reply ran past
the longest reply after the thinking: the counts and the reason as the
server gave them. Every answer here is invented.
"""

from __future__ import annotations

import pytest

from evals.compare_models import _EMPTY_REPLY
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelErrorKind,
    Picture,
    PictureKind,
    Role,
)
from tests.llm.fake_server import SETTINGS, FakeServer, chat_reply, json_response

ASKED = [Message(Role.USER, "Which fruit did the invented stall sell most?")]
PICTURE = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
THOUGHT = "The stall sold three apples and two pears, so"


def fails(answer: dict[str, object], *, pictures: bool) -> ModelError:
    server = FakeServer([json_response(200, answer)])
    model = OllamaModel(SETTINGS, transport=server.transport)
    with pytest.raises(ModelError) as caught:
        if pictures:
            model.chat_with_pictures(ASKED, [PICTURE])
        else:
            model.chat(ASKED)
    return caught.value


def thinking_reply(content: str, done_reason: str = "stop") -> dict[str, object]:
    return chat_reply(
        message={"role": "assistant", "content": content, "thinking": THOUGHT},
        done_reason=done_reason,
    )


@pytest.mark.parametrize("pictures", [False, True], ids=["chat", "with pictures"])
@pytest.mark.parametrize("content", ["", "   ", "\n\t "], ids=["empty", "spaces", "blanks"])
def test_a_blank_reply_is_malformed_in_the_words_counted(content: str, *, pictures: bool) -> None:
    error = fails(chat_reply(content), pictures=pictures)

    assert error.kind is ModelErrorKind.MALFORMED_REPLY
    assert _EMPTY_REPLY in error.message
    assert _EMPTY_REPLY in str(error)


@pytest.mark.parametrize("pictures", [False, True], ids=["chat", "with pictures"])
def test_a_reply_with_only_thinking_is_an_empty_reply_and_says_so(*, pictures: bool) -> None:
    error = fails(thinking_reply(""), pictures=pictures)

    assert error.kind is ModelErrorKind.MALFORMED_REPLY
    assert _EMPTY_REPLY in str(error)
    assert error.message.endswith("has an empty reply; the model wrote only its thinking")


@pytest.mark.parametrize("pictures", [False, True], ids=["chat", "with pictures"])
def test_thinking_that_reached_the_longest_reply_is_said_too(*, pictures: bool) -> None:
    error = fails(thinking_reply("", done_reason="length"), pictures=pictures)

    assert _EMPTY_REPLY in str(error)
    assert error.message.endswith(
        "has an empty reply; the model wrote only its thinking, and reached the longest reply"
    )


def test_blank_thinking_says_only_that_the_reply_is_empty() -> None:
    answer = chat_reply(message={"role": "assistant", "content": "", "thinking": "  "})

    assert fails(answer, pictures=False).message == "the model server's answer has an empty reply"


def test_a_reply_beside_some_thinking_is_the_reply() -> None:
    server = FakeServer([json_response(200, thinking_reply('{"fruit": "apple"}'))])

    reply = OllamaModel(SETTINGS, transport=server.transport).chat(ASKED)

    assert reply.text == '{"fruit": "apple"}'


def test_a_reply_past_the_longest_after_thinking_is_recorded_as_the_server_said() -> None:
    # As Ollama answered with a schema: the thinking ended under the longest
    # reply, the reply ran past it, and the model stopped by itself.
    answer = thinking_reply('{"fruit": "apple"}', done_reason="stop")
    answer["eval_count"] = SETTINGS.max_reply_tokens + 50
    server = FakeServer([json_response(200, answer)])

    reply = OllamaModel(SETTINGS, transport=server.transport).chat(ASKED)

    assert reply.record.reply_tokens == SETTINGS.max_reply_tokens + 50
    assert reply.record.finish is FinishReason.STOPPED
    assert reply.text == '{"fruit": "apple"}'
